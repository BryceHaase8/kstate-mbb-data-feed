#!/usr/bin/env python3
"""NIL Estimation Model: ESPN-native Bayesian in-season publisher.

The fitted CatBoost model (market-price proxy distilled from V4) must remain PRIVATE.
Only ID-keyed, source-versioned predictions may be published to the site's public feed.
The *prior* is frozen once at launch from 2025-26 (or latest completed) stats;
current-season updates are calculated independently from that fixed prior.

The exposure weights below are a transparent INITIAL policy, not a historically
calibrated optimum. Staff can inspect or change them after real checkpoint testing.
"""
from __future__ import annotations
import argparse, hashlib, json, math, pathlib, datetime, sys
import joblib
HERE=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import features as old
from season_features import enrich, make_catboost_row
MODEL=HERE/'nil_estimation_model_core_shadow.joblib'
RELEASE='nil-estimation-bayesian-v2-2026-10-24'
FLOOR=20_000
FULL_GAMES=30
STATS=('pts','reb','ast','stl','blk','tov','pf','oreb','dreb','fga','two_pa','three_pa','fta')
MAKES=('two_pm','three_pm','ftm')

def num(x,default=0.):
 try:
  v=float(x);return v if math.isfinite(v) else default
 except (ValueError,TypeError):return default

def clamp(v,lo,hi):return max(lo,min(hi,v))

def weighted(a,b,w):return a*(1-w)+b*w

def past_seasons(entry,year):
 return sorted([r for r in entry.get('seasons',[]) if int(num(r.get('season'))) <year and num(r.get('gp'))>0],key=lambda r:int(r['season']),reverse=True)

def get_player_season(entry,year):
 # Prefer explicit season row, not latest when a player has DNP or is missing.
 rows=[r for r in entry.get('seasons',[]) if int(num(r.get('season'))) ==year]
 if rows:return rows[-1]
 latest=entry.get('latest') or {}
 return latest if int(num(latest.get('season'))) ==year else None

def context_for_year(history,year,team_id, current_team=None):
 if year==2027:return (current_team or {}).get(str(team_id))
 return (((history.get('teams') or {}).get(str(year)) or {}).get('teams') or {}).get(str(team_id))

def score_model(model_asset,row,all_prior,season,team):
 feat=enrich(old.feat(row,all_prior,team),row,all_prior,season,team)
 xx=[make_catboost_row(feat,model_asset['features'])]
 pred=model_asset['student'].predict(xx) if model_asset.get('type')=='catboost' else model_asset['student'].predict([feat])
 raw=math.exp(float(pred[0]))
 if not math.isfinite(raw):raise ValueError('Nonfinite model prediction')
 return int(round(clamp(raw,FLOOR,20_000_000)))

def blended_shooting(makes,attempts,prev_pct,pseudo_attempts,league_pct):
 baseline=clamp(prev_pct if prev_pct is not None else league_pct,.04,.96)
 return clamp((max(0,num(makes))+baseline*pseudo_attempts)/(max(0,num(attempts))+pseudo_attempts),.02,.98)

def preview_rates(cur,prior):
 """Stabilized per-30 rates, with stat-specific priors.

 Rate evidence must not be shrunk twice with a 260-minute blanket prior:
 at 900 current minutes scoring volume should predominantly reflect this season.
 Shooting *accuracy* has its own attempt prior, preserving genuine uncertainty.
 These are preseason policy constants, not price-optimized market parameters.
 """
 cm=num(cur.get('minutes'));pm=num(prior.get('minutes'))
 fallback={ 'pts':9.,'reb':4.5,'ast':2.,'stl':1.,'blk':.5,'tov':1.5,'pf':2.,'oreb':1.,'dreb':3.5,
           'fga':9.,'two_pa':6.,'three_pa':3.,'fta':3. }
 # Faster-changing activity, usage, and scoring volume than scarce defensive events.
 prior_equivalent_minutes={'pts':85,'reb':110,'ast':130,'stl':190,'blk':190,
          'tov':120,'pf':125,'oreb':130,'dreb':110,'fga':90,
          'two_pa':95,'three_pa':115,'fta':115}
 z={}
 for k in STATS:
  pr=num(prior.get(k))*30/pm if pm>0 else fallback[k]
  cu=num(cur.get(k))*30/cm if cm>0 else pr
  pseudo=prior_equivalent_minutes[k]*(1 if pm>=150 else .55)
  weight=cm/(cm+pseudo) if cm>0 else 0.
  z[k]=clamp(weighted(pr,cu,weight),0,100 if k=='pts' else 40)
 z['fga']=z['two_pa']+z['three_pa']
 def pct(row,pmk,ak,field,fallback):
  a=num(row.get(ak));p=num(row.get(pmk))
  if a>0:return clamp(p/a,0,1)
  val=row.get(field);return clamp(num(val,fallback),0,1)
 prior_2=pct(prior,'two_pm','two_pa','two_pt_pct',.51) if pm>=60 else .51
 prior_3=pct(prior,'three_pm','three_pa','three_pt_pct',.34) if pm>=60 else .34
 prior_f=pct(prior,'ftm','fta','ft_pct',.72) if pm>=60 else .72
 # Ability priors are stronger for scarce events than volume/rates; at 30 games
 # these can still reflect a mature prior, which is the intended Bayesian logic.
 z['two_pct']=blended_shooting(cur.get('two_pm'),cur.get('two_pa'),prior_2,65 if pm>=150 else 35,.51)
 z['three_pct']=blended_shooting(cur.get('three_pm'),cur.get('three_pa'),prior_3,80 if pm>=150 else 45,.34)
 z['ft_pct']=blended_shooting(cur.get('ftm'),cur.get('fta'),prior_f,40 if pm>=150 else 20,.72)
 z['pts']=2*z['two_pa']*z['two_pct']+3*z['three_pa']*z['three_pct']+z['fta']*z['ft_pct']
 return z

def player_weight(gp,minutes,prior_minutes,prior_games):
 """Nonlinear Bayesian-style evidence gate with both GP and MPG.

 For an established returner: 30 x 30 MPG ~=91% new-season direct NIL
 weight, 30 x 6 MPG ~=79%. Each appearance matters even at low minutes,
 without treating one 30-minute appearance as a full-season breakout.
 A more uncertain preseason baseline (weak prior playing time) relaxes K.
 This is an explicit policy, not a learned posterior or market calibration.
 """
 gp=num(gp);minutes=num(minutes)
 if gp<=0 or minutes<=0:return 0.,0.
 average=clamp(minutes/gp,0,42)
 effective=gp*(.40+.60*clamp(average/22,0,1.55)**.75)
 prior_strength=8.5 if prior_minutes>=300 and prior_games>=12 else 6.5 if prior_minutes>=90 else 5.5
 exponent=1.65
 evidence=effective**exponent
 weight=evidence/(evidence+prior_strength**exponent)
 return clamp(weight,0,.999),effective

def stabilized_virtual_season(cur, prior, year,team_games=None):
 gp=num(cur.get('gp'));m=num(cur.get('minutes'))
 if gp<1 or m<=0:raise ValueError('Current player has no minutes')
 prior_m=num(prior.get('minutes')); prior_g=num(prior.get('gp'))
 old_role=clamp(prior_m/prior_g if prior_g>0 else 9,0,40)
 # Minutes in verified *appearances* measure on-court role. Team DNPs can
 # be injury/eligibility-related and do not by themselves prove benching.
 # We intentionally do not divide minutes by team games without a validated
 # availability/rotation designation for every missed game.
 observed_role=clamp(m/gp,0,40)
 role_w=1-math.exp(-gp/(4.5 if prior_m>=150 else 3.5))
 role_mpg=clamp(weighted(old_role,observed_role,role_w),0,40)
 rates=preview_rates(cur,prior)
 v={'season':year,'seasonLabel':f'{year-1}-{str(year)[-2:]}',
    'name':cur.get('name') or prior.get('name'), 'team':cur.get('team') or prior.get('team'),
    'teamId':cur.get('teamId'),'position':cur.get('position') or prior.get('position'),
    'gp':FULL_GAMES,'gs':FULL_GAMES*weighted(num(prior.get('gs'))/max(1,prior_g),num(cur.get('gs'))/gp,role_w),
    'minutes':FULL_GAMES*max(.1,role_mpg),'mpg':role_mpg}
 for k in STATS:
  v[k]=rates[k]*v['minutes']/30
 v['fga']=v['two_pa']+v['three_pa']
 v['two_pm']=v['two_pa']*rates['two_pct'];v['three_pm']=v['three_pa']*rates['three_pct']
 v['fgm']=v['two_pm']+v['three_pm'];v['ftm']=v['fta']*rates['ft_pct']
 v['pts']=2*v['two_pm']+3*v['three_pm']+v['ftm']
 for k,tot in [('ppg','pts'),('rpg','reb'),('apg','ast')]:v[k]=v[tot]/FULL_GAMES
 v['two_pt_pct']=rates['two_pct'];v['three_pt_pct']=rates['three_pct'];v['ft_pct']=rates['ft_pct']
 v['efg_pct']=(v['fgm']+.5*v['three_pm'])/v['fga'] if v['fga'] else None
 v['ts_pct']=v['pts']/(2*(v['fga']+.44*v['fta'])) if (v['fga']+.44*v['fta'])>0 else None
 v['fg_pct']=v['fgm']/v['fga'] if v['fga'] else None
 return v,role_w

def verified_context(x,year,asof):
 # Only signed-off schema/stage. Preseason forecast intentionally allowed.
 if x.get('season')!=year or not isinstance(x.get('teams'),list) or not 300<=len(x['teams'])<=400:
  raise ValueError('Season team context does not match or has too few teams')
 t=str(x.get('retrievedAtUTC') or '')[:10]
 if not t or t>asof:raise ValueError('Team context must predate scoring as-of date')
 out={}
 for row in x['teams']:
  id=str(row.get('espnTeamId') or '')
  if id.isdigit() and num(row.get('rank'))>0:
   out[id]={'rank':row['rank'],'rankTotal':len(x['teams']),'conference':row.get('conference'),'adjEM':row.get('adjEM')}
 if len(out)<300:raise ValueError('Insufficient ESPN-team identity coverage')
 return out

def run(players_file,archived_context_file, current_context_file, asof,output, min_coverage=0.5, team_games_file=None):
 # When publishable source is from the future, fail instead of constructing
 # fake historical checkpoints from full-season aggregates.
 asof=datetime.date.fromisoformat(asof).isoformat()
 payload=json.loads(pathlib.Path(players_file).read_text()); historic=json.loads(pathlib.Path(archived_context_file).read_text())
 if payload.get('schemaVersion') not in (1,2,3):raise ValueError('Unknown factual schema')
 generated=str(payload.get('generatedAt') or '')[:10]
 if not generated or generated>asof:raise ValueError('Factual stats are not a verified as-of snapshot')
 # Once current-season games exist, do not quietly issue fresh NIL prices
 # using a stale national snapshot. During preseason an archived source can
 # remain valid without falsely claiming current games have arrived.
 if int(payload.get('latestSeason') or 0)>=2027 and (datetime.date.fromisoformat(asof)-datetime.date.fromisoformat(generated)).days>3:
  raise ValueError('Current season ESPN box feed is stale (>3 days)')
 newctx=None
 if current_context_file:
  ctx_data=json.loads(pathlib.Path(current_context_file).read_text());newctx=verified_context(ctx_data,2027,asof)
  if int(payload.get('latestSeason') or 0)>=2027:
   rating_date=str(ctx_data.get('retrievedAtUTC') or '')[:10]
   if (datetime.date.fromisoformat(asof)-datetime.date.fromisoformat(rating_date)).days>7:
    raise ValueError('Current-season team-strength feed is stale (>7 days)')
 if int(payload.get('latestSeason') or 0)>=2027 and newctx is None:
  raise ValueError('Current-season scoring requires matching team-strength data')
 games={}
 if team_games_file:
  raw=json.loads(pathlib.Path(team_games_file).read_text())
  if int(raw.get('season') or 0)!=2027 or str(raw.get('asOf') or '')[:10]>asof:
   raise ValueError('Verified team-game counts have wrong season/date')
  games={str(k):int(v) for k,v in raw.get('teamGames',{}).items() if str(k).isdigit() and 0<=int(v)<=40}
 asset=joblib.load(MODEL);allrows={};stats={'2026_based':0,'older_season_based':0,'current_updated':0,'current_missing_context':0,'roster_without_prior':0,'no_prior_model':0,'current_without_2027':0}
 for athlete,entry in sorted((payload.get('players') or {}).items()):
  if not str(athlete).isdigit():continue
  past=past_seasons(entry,2027)
  prior=None;prior_season=None;baseline=None
  for candidate in past:
   yr=int(candidate['season']); ctx=context_for_year(historic,yr,candidate.get('teamId'))
   if not ctx or num(ctx.get('rank'))<=0:continue
   try:baseline=score_model(asset,candidate,[p for p in past if int(p['season'])<yr],yr,ctx)
   except Exception:continue
   prior=candidate;prior_season=yr;break
  current=get_player_season(entry,2027)
  if baseline is None:
   stats['roster_without_prior']+=1
   if not current:continue
  elif prior_season==2026:stats['2026_based']+=1
  else:stats['older_season_based']+=1
  score=baseline;current_price=None;w=0;role_w=0;gp=num((current or {}).get('gp'));minutes=num((current or {}).get('minutes'))
  status='PRESEASON_BASELINE' if baseline else 'UNPRICED_NO_PRIOR'
  team_id=str((current or {}).get('teamId') or '')
  if current and gp>0 and minutes>0:
   if not newctx or team_id not in newctx:
    stats['current_missing_context']+=1;status='MISSING_CURRENT_TEAM_CONTEXT'
   else:
    # No valid prior: require adequate independent current-season evidence.
    if prior is None:prior={'gp':0,'minutes':0,'gs':0,'position':current.get('position')}
    virtual,role_w=stabilized_virtual_season(current,prior,2027,games.get(team_id))
    try:
     current_price=score_model(asset,virtual,past,2027,newctx[team_id]);
     w,effective=player_weight(gp,minutes,num(prior.get('minutes')),num(prior.get('gp')))
     if baseline:
      score=int(round(math.exp((1-w)*math.log(baseline)+w*math.log(current_price))))
      status='UPDATED' if w>.005 else 'PRESEASON_BASELINE'
     elif gp>=5 and minutes>=100:
      # This is a *candidate* current-season prediction, not a value replacing
      # a freshman's verified HS baseline. Site will blend it via output weight.
      score=current_price;status='NEW_PLAYER_PROVISIONAL'
     else:score=None;status='NEW_PLAYER_INSUFFICIENT_EVIDENCE'
     if score:stats['current_updated']+=1
    except Exception as exc:status='SCORING_ERROR';current_price=None;score=baseline
  elif baseline:stats['current_without_2027']+=1
  if score is None:continue
  # No end-to-end website cash change if as-of fails. Prices published as
  # full replacement snapshot and can always be rolled back to V4 fallback.
  allrows[str(athlete)]={'value':int(score),'preseason':baseline,'currentOnly':current_price,
   'season':2027,'priorSeason':prior_season,'games':int(gp),'minutes':round(minutes,2),
   'weight':round(w,5),'roleWeight':round(role_w,5),'status':status,
   'evidenceGP':int(gp),'evidenceMPG':round(minutes/gp,2) if gp else 0}
 cover=stats['2026_based']+stats['older_season_based'];coverage=cover/max(1,len(payload.get('players') or {}))
 if cover<100 or coverage<min_coverage:raise ValueError(f'Baseline coverage unexpectedly low: {cover}/{len(payload.get("players") or {})}')
 out={'schemaVersion':1,'model':'NIL Estimation Model','release':RELEASE,'season':2027,
  'generatedAt':asof+'T00:00:00Z','factualGeneratedAt':payload.get('generatedAt'),
  'target':'open-market transfer NIL estimate; not actual compensation or asking price',
  'inputContext':'2025-26 stats prior; 2026-27 verified box stats; nonlinear games/minutes Bayes-v2 policy',
  'policyVersion':2,'weightPolicy':'nonlinear_games_and_minutes_1.65; 30x30 ~91% direct weight',
  'productionModelFrozen':True, 'playerCount':len(allrows),'byESPNId':allrows}
 dest=pathlib.Path(output);dest.parent.mkdir(parents=True,exist_ok=True)
 dest.write_text(json.dumps(out,separators=(',',':'))+'\n')
 def sha(path):return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest() if path else None
 manifest={'release':RELEASE,'asOf':asof,'count':len(allrows),'baseCoverage':coverage,'stats':stats,
  'sha256':{'factual':sha(players_file),'historicalTeam':sha(archived_context_file),'currentTeam':sha(current_context_file),'teamGames':sha(team_games_file),'model':sha(MODEL)},
  'safety':{'joins':'ESPN-ID only','liveStatsAsOfChecked':True,'currentTeamSeasonMatch':bool(current_context_file),'marketGroundTruthVerified':False,'liveSiteWrites':False}}
 (dest.parent/(dest.name+'.manifest.json')).write_text(json.dumps(manifest,indent=2)+'\n')
 return manifest

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--factual',required=True);ap.add_argument('--archived-teams',required=True);ap.add_argument('--current-teams');ap.add_argument('--as-of',required=True);ap.add_argument('--output',required=True);ap.add_argument('--team-games');ap.add_argument('--min-coverage',type=float,default=.5)
 a=ap.parse_args();print(json.dumps(run(a.factual,a.archived_teams,a.current_teams,a.as_of,a.output,a.min_coverage,a.team_games),indent=2))
