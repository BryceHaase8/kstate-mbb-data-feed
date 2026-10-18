#!/usr/bin/env python3
"""Daily ESPN/hoopR RAPM experiment. Independent of main Portal player feed.

Five-man lineups come from ESPN starters and substitution events.
Possession outcomes use the existing Phase 2 event state machine. Ratings
are research-only and not promoted into Portal player evaluations.
"""
import argparse,csv,datetime,json,collections,os,sys,math
from pathlib import Path
import pandas as pd
import numpy as np
from scipy.sparse import coo_matrix,hstack
from sklearn.linear_model import Ridge

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from rapm_lineups import audit_game
from rapm_possessions_v2 import run_one,matchup_index

PBP_REQUIRED={'game_id','period_number','seconds_remaining_period','home_team_id','away_team_id','team_id','event_type','text','home_score','away_score','athlete_id_1'}
BOX_REQUIRED={'game_id','team_id','athlete_id','starter','minutes'}

def get_team_starters(box):
    starters=collections.defaultdict(set)
    for _,r in box.iterrows():
        if str(r.get('starter','')).lower() in ('true','1','t') and pd.notna(r.athlete_id):
            starters[str(r.team_id)].add(str(r.athlete_id))
    return starters

def model_fit(possessions,alpha=1000.0,target='points',torvik=None):
    ids=sorted(set(v for p in possessions for key in ('off_players','def_players') for v in p[key].split('|')))
    teams=sorted(set(v for p in possessions for key in ('off_team','def_team') for v in [p[key]]))
    pi={p:i for i,p in enumerate(ids)};ti={t:i for i,t in enumerate(teams)}
    n=len(possessions); npid=len(ids); nt=len(teams)
    rows=[];cols=[];values=[]; trows=[];tcols=[];tvalues=[]
    exposure=collections.Counter()
    for i,p in enumerate(possessions):
        trows.extend((i,i));tcols.extend((ti[p['off_team']], nt+ti[p['def_team']]));tvalues.extend((1,1))
        for pid in p['off_players'].split('|'):
            rows.append(i);cols.append(pi[pid]);values.append(1);exposure[pid]+=1
        for pid in p['def_players'].split('|'):
            rows.append(i);cols.append(npid+pi[pid]);values.append(-1);exposure[pid]+=1
    base=coo_matrix((tvalues,(trows,tcols)),shape=(n,2*nt)).tocsr()
    player=coo_matrix((values,(rows,cols)),shape=(n,2*npid)).tocsr()
    X=hstack([base,player],format='csr')
    y=np.fromiter((p[target] for p in possessions),dtype=float,count=n)
    if torvik is not None:
        oe=np.mean([v[0] for v in torvik.values()])
        de=np.mean([v[1] for v in torvik.values()])
        y-=np.fromiter(((torvik[p['off_team']][0]-oe+torvik[p['def_team']][1]-de)/100
                         for p in possessions),dtype=float,count=n)
    reg=Ridge(alpha=alpha,solver='lsqr',tol=1e-5).fit(X,y)
    beta=reg.coef_[2*nt:]
    # Sign: defensive player -1 in design so positive defense coefficient suppresses opponent scoring.
    return [{'espnAthleteId':pid,'offRAPM':round(100*float(beta[i]),2),
             'defRAPM':round(100*float(beta[npid+i]),2),
             'totalRAPM':round(100*float(beta[i]+beta[npid+i]),2),
             'cleanPossessionExposure':int(exposure[pid])} for i,pid in enumerate(ids)]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--pbp',default='rapm_input/pbp.csv')
    ap.add_argument('--box',default='rapm_input/box.csv')
    ap.add_argument('--output',default='public/rapm_research.json')
    ap.add_argument('--audit',default='public/rapm_research_audit.json')
    ap.add_argument('--season',type=int,default=None)
    ap.add_argument('--max-games',type=int,default=0)
    ap.add_argument('--torvik',default='research_qa/torvik_team_strength_2026.csv')
    a=ap.parse_args()
    if a.season is None:
        raw=os.getenv('TARGET_SEASON','').strip()
        today=datetime.date.today()
        a.season=int(raw) if raw else today.year + (today.month>=7)
    if not Path(a.pbp).is_file() or not Path(a.box).is_file():
        print('RAPM: no hoopR active-season games yet; preserving last published result');return
    # Historical test: Torvik team conditioning deliberately omitted.
    # Empirical Bayes shooter baseline: leave the current game out of the
    # estimate. This remains retrospective; not a time-forward forecast.
    global_counts=collections.Counter();game_counts=collections.Counter()
    participants=collections.defaultdict(set)
    with open(a.pbp,encoding='utf-8-sig',newline='') as f:
        for e in csv.DictReader(f):
            typ=e.get('event_type')
            if typ not in ('2PT Shot','MadeFreeThrow'):continue
            shooter=e.get('athlete_id_1','').strip()
            if not shooter:continue
            if typ=='2PT Shot':
                sv=str(e.get('shot_value','')).strip()
                if sv not in ('3','3.0') and 'three point' not in str(e.get('text','')).lower():
                    continue
                kind='three'
                made=str(e.get('shot_made','')).lower()=='true' or ' makes ' in (' '+str(e.get('text','')).lower()+' ')
            else:
                kind='ft'
                made=(' makes ' in (' '+str(e.get('text','')).lower()+' ') or ' made ' in (' '+str(e.get('text','')).lower()+' '))
            gid=e['game_id'];global_counts[(kind,shooter,'n')]+=1
            game_counts[(gid,kind,shooter,'n')]+=1
            if made:
                global_counts[(kind,shooter,'m')]+=1
                game_counts[(gid,kind,shooter,'m')]+=1
            participants[gid].add(shooter)
    def shooter_rates(gid):
        out={'three':{},'ft':{},'defaultThree':.337,'defaultFT':.722}
        for shooter in participants.get(gid,()):
            for kind,prior,weight in [('three',.337,60),('ft',.722,35)]:
                n=global_counts[(kind,shooter,'n')]-game_counts[(gid,kind,shooter,'n')]
                made=global_counts[(kind,shooter,'m')]-game_counts[(gid,kind,shooter,'m')]
                out[kind][shooter]=(made+prior*weight)/(n+weight)
        return out
    box=pd.read_csv(a.box,dtype={'game_id':str,'team_id':str,'athlete_id':str})
    missing=BOX_REQUIRED-set(box.columns)
    if missing:raise ValueError('Missing box columns: '+str(sorted(missing)))
    bb={gid:g for gid,g in box.groupby('game_id',sort=False)}
    included=[];results=[];reasons=collections.Counter();poss_totals=collections.Counter()
    n=0
    skipped_missing_torvik=0
    with open(a.pbp,encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        absent=PBP_REQUIRED-set(reader.fieldnames or [])
        if absent:raise ValueError('Missing PBP columns: '+str(sorted(absent)))
        current_gid=None;records=[]
        def process_game(gid,records):
            nonlocal skipped_missing_torvik
            if gid not in bb:return
            b=bb[gid]
            official=get_team_starters(b)
            outcome=audit_game(records,official_first_half=official)
            good=[period for period in outcome['results'] if period['ok']]
            entry={'game_id':gid,'status':'excluded','reason':'','possessions':0,
                   'periodsTotal':outcome['periods'],'periodsValid':len(good),
                   'possiblePlayerMinutes':sum(p['expected_duration'] for p in outcome['results'])*10/60}
            if not good:
                entry['reason']='no_valid_periods';reasons[entry['reason']]+=1;results.append(entry);return
            full=(len(good)==outcome['periods'])
            stints=[s for p in good for s in p['stints']]
            rec=collections.Counter()
            for stint in stints:
                for pid in (stint['home_players']+'|'+stint['away_players']).split('|'):
                    rec[pid]+=float(stint['duration_s'])/60
            mins={str(r.athlete_id):float(r.minutes) for _,r in b.iterrows()
                  if pd.notna(r.athlete_id) and pd.notna(r.minutes)}
            unknown=set(rec)-set(mins)
            diff=max((abs(rec.get(pid,0)-m) for pid,m in mins.items()),default=999)
            minute_ok= len(mins)>=10 and not unknown and (
                diff<=1.01 if full else all(rec.get(pid,0)<=m+1.01 for pid,m in mins.items()))
            entry['minuteVerified']=bool(minute_ok)
            if not minute_ok:
                entry['reason']='official_minutes_mismatch';reasons[entry['reason']]+=1;results.append(entry);return
            entry['verifiedPlayerMinutes']=sum(p['duration'] for p in good)*10/60
            indexed=matchup_index(pd.DataFrame(stints))
            ps,flags,stats,final=run_one(gid,pd.DataFrame(records),indexed,luck_rates=shooter_rates(gid))
            home=str(records[0]['home_team_id']);away=str(records[0]['away_team_id'])
            totals=collections.Counter()
            for p in ps:totals[p['off_team']]+=p['points']
            gap={home:final[0]-totals[home],away:final[1]-totals[away]}
            clean=[p for p in ps if p['flags'] in ('','and_one') and 0<=p['points']<=4 and
                    len(p['off_players'].split('|'))==5 and len(p['def_players'].split('|'))==5]
            ratio=len(clean)/len(ps) if ps else 0
            count_diff=max(abs(stats[t]['poss_diff']) for t in (home,away))
            entry['candidatePossessions']=len(ps)
            entry['cleanPossessionFraction']=round(ratio,4)
            entry['scoreGap']=gap if full else None
            if full and (max(abs(v) for v in gap.values())>6 or sum(abs(v) for v in gap.values())>8):
                entry['reason']='score_gap'
            elif count_diff>6:
                entry['reason']='possession_count_gap'
            elif len(clean)<50 or ratio<(.80 if full else .75):
                entry['reason']='insufficient_clean_possessions'
            if entry['reason']:
                reasons[entry['reason']]+=1;results.append(entry);return
            entry['status']='accepted_full' if full else 'accepted_partial'
            entry['possessions']=len(clean)
            included.extend(clean);results.append(entry)
        for record in reader:
            gid=record['game_id']
            if current_gid is not None and gid!=current_gid:
                process_game(current_gid,records);n+=1
                if a.max_games and n>=a.max_games:break
                records=[]
            current_gid=gid;records.append(record)
        else:
            if records:process_game(current_gid,records);n+=1
    processed=len(results)
    accepted=[x for x in results if x['status'].startswith('accepted')]
    accepted_n=len(accepted)
    possible_min=sum(x['possiblePlayerMinutes'] for x in results)
    used_min=sum(x.get('verifiedPlayerMinutes',0) for x in accepted)
    clean_candidates=sum(x.get('candidatePossessions',0) for x in accepted)
    report={'schemaVersion':1,'season':a.season,'status':'RESEARCH_ONLY_NOT_FOR_PORTAL',
        'generatedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'gamesWithOfficialBox':processed,'gamesUsedInFit':accepted_n,
        'fullGamesUsed':sum(x['status']=='accepted_full' for x in accepted),
        'partialGamesUsed':sum(x['status']=='accepted_partial' for x in accepted),
        'minutesCoverageInFit':round(used_min/possible_min,4) if possible_min else 0,
        'officialBoxVerifiedPlayerMinutesUsed':round(used_min),
        'totalPossiblePlayerMinutes':round(possible_min),
        'cleanPossessionsUsed':len(included),
        'cleanShareInAccepted':round(len(included)/clean_candidates,4) if clean_candidates else 0,
        'exclusionReasons':dict(reasons),'gameDetails':results,
        'note':'Requires full ESPN game official-minute reconciliation or partial-period minute upper bound. Never publish ratings to the Portal.'}
    output=Path(a.output);audit=Path(a.audit)
    output.parent.mkdir(parents=True,exist_ok=True);audit.parent.mkdir(parents=True,exist_ok=True)
    audit.write_text(json.dumps(report,separators=(',',':'))+'\n')
    if accepted_n<100 or len(included)<10000:
        print('Insufficient validated data, no RAPM fit',accepted_n,len(included));return
    # Exact same official-minute-gated possessions under all four outcomes.
    variants={
      'baselineV1':model_fit(included,alpha=1000,target='points',torvik=None),
      'luckAdjusted':model_fit(included,alpha=1000,target='pointsLuckAdjusted',torvik=None)
    }
    ratings=variants['luckAdjusted']
    baseline={r['espnAthleteId']:r for r in variants['baselineV1']}
    for v in ratings:
        old=baseline[v['espnAthleteId']]
        v['baselineV1TotalRAPM']=old['totalRAPM']
        v['deltaVersusV1']=round(v['totalRAPM']-old['totalRAPM'],2)
    covered3=sum(p['luck3Attempts'] for p in included)
    coveredft=sum(p['luckFTAttempts'] for p in included)
    delta=sum(p['luckDelta'] for p in included)
    report['torvikMissingGameExclusions']=skipped_missing_torvik
    report['luck3AttemptsAttributed']=covered3
    report['luckFTAttemptsAttributed']=coveredft
    report['luckDeltaPointsTotal']=round(delta,3)
    report['variantsCompared']=list(variants)
    summary={}
    for label,v in variants.items():
        d={r['espnAthleteId']:r['totalRAPM'] for r in v}
        for other,ww in variants.items():
            if other==label:continue
            e={r['espnAthleteId']:r['totalRAPM'] for r in ww}
            common=[p for p in d if p in e]
            summary[label+'_vs_'+other]=round(float(np.corrcoef([d[p] for p in common],[e[p] for p in common])[0,1]),4)
    report['ratingCorrelations']=summary
    audit.write_text(json.dumps(report,separators=(',',':'))+'\n')
    payload={'schemaVersion':1,'season':a.season,'status':'RESEARCH_ONLY_NOT_FOR_PORTAL',
        'gamesAccepted':accepted_n,'verifiedPlayerMinutesUsed':round(used_min),
        'verifiedMinuteCoverageInFit':report['minutesCoverageInFit'],
        'cleanPossessions':len(included),'ridgeAlpha':1000,
        'units':'points_per_100_possessions','ratings':ratings,
        'variants':variants,'modelNotes':{'torvik':'NOT USED in this 2025 historical predictive test','luck':'Posterior shooter 3P/FT means estimated excluding same game'}}
    output.write_text(json.dumps(payload,separators=(',',':'))+'\n')
    print('OFFICIAL BOX RAPM V2 COMPARISON',len(ratings),'players',len(included),'clean possessions',flush=True)
if __name__=='__main__':main()
