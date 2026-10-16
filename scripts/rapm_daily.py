#!/usr/bin/env python3
"""Daily ESPN/hoopR RAPM experiment. Independent of main Portal player feed.

Five-man lineups come from ESPN starters and substitution events.
Possession outcomes use the existing Phase 2 event state machine. Ratings
are research-only and not promoted into Portal player evaluations.
"""
import argparse,csv,datetime,json,collections,os,sys
from pathlib import Path
import pandas as pd
import numpy as np
from scipy.sparse import coo_matrix,hstack
from sklearn.linear_model import Ridge

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from rapm_lineups import audit_game
from rapm_possessions import run_one,matchup_index

PBP_REQUIRED={'game_id','period_number','seconds_remaining_period','home_team_id','away_team_id','team_id','event_type','text','home_score','away_score','athlete_id_1'}
BOX_REQUIRED={'game_id','team_id','athlete_id','starter','minutes'}

def get_team_starters(box):
    starters=collections.defaultdict(set)
    for _,r in box.iterrows():
        if str(r.get('starter','')).lower() in ('true','1','t') and pd.notna(r.athlete_id):
            starters[str(r.team_id)].add(str(r.athlete_id))
    return starters

def model_fit(possessions,alpha=1000.0):
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
    y=np.fromiter((p['points'] for p in possessions),dtype=float,count=n)
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
    a=ap.parse_args()
    if a.season is None:
        raw=os.getenv('TARGET_SEASON','').strip()
        today=datetime.date.today()
        a.season=int(raw) if raw else today.year + (today.month>=7)
    if not Path(a.pbp).is_file() or not Path(a.box).is_file():
        print('RAPM: no hoopR active-season games yet; preserving last published result');return
    box=pd.read_csv(a.box,dtype={'game_id':str,'team_id':str,'athlete_id':str})
    missing=BOX_REQUIRED-set(box.columns)
    if missing:raise ValueError('Missing box columns: '+str(sorted(missing)))
    bb={gid:g for gid,g in box.groupby('game_id',sort=False)}
    included=[];results=[];reasons=collections.Counter();poss_totals=collections.Counter()
    n=0
    with open(a.pbp,encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        absent=PBP_REQUIRED-set(reader.fieldnames or [])
        if absent:raise ValueError('Missing PBP columns: '+str(sorted(absent)))
        current_gid=None;records=[]
        def process_game(gid,records):
            if gid not in bb:return
            b=bb[gid]
            official=get_team_starters(b)
            outcome=audit_game(records,official_first_half=official)
            entry={'game_id':gid,'status':'excluded','reason':'','possessions':0}
            if not outcome['ok']:
                entry['reason']='lineup_'+str(next((k['reason'] for k in outcome['results'] if not k['ok']), 'unknown'))
                reasons['lineup']+=1;results.append(entry);return
            # Official starter and minute checks, prior to modeling.
            all_stints=[x for per in outcome['results'] for x in per['stints']]
            recmins=collections.Counter()
            for s in all_stints:
                for player in (s['home_players']+'|'+s['away_players']).split('|'):
                    recmins[player]+=float(s['duration_s'])/60
            official_mins={str(r.athlete_id):float(r.minutes) for _,r in b.iterrows() if pd.notna(r.athlete_id) and pd.notna(r.minutes)}
            if len(official_mins)<10 or any(abs(recmins.get(pid,0)-mn)>1.01 for pid,mn in official_mins.items()):
                entry['reason']='official_minutes_mismatch';reasons[entry['reason']]+=1;results.append(entry);return
            indexed=matchup_index(pd.DataFrame(all_stints))
            df=pd.DataFrame(records)
            ps,flags,stats,final=run_one(gid,df,indexed)
            home=str(records[0]['home_team_id']);away=str(records[0]['away_team_id'])
            totals=collections.Counter()
            for p in ps:totals[p['off_team']]+=p['points']
            if totals[home]!=final[0] or totals[away]!=final[1]:
                entry['reason']='possession_score_mismatch';reasons[entry['reason']]+=1;results.append(entry);return
            if max(abs(stats[t]['poss_diff']) for t in (home,away))>5:
                entry['reason']='possession_count_mismatch';reasons[entry['reason']]+=1;results.append(entry);return
            clean=[p for p in ps if p['flags'] in ('','and_one') and 0<=p['points']<=4 and 
                len(p['off_players'].split('|'))==5 and len(p['def_players'].split('|'))==5]
            if len(clean)<.8*len(ps):
                entry['reason']='too_many_ambiguous_possessions';reasons[entry['reason']]+=1;results.append(entry);return
            entry['status']='accepted';entry['reason']='';entry['possessions']=len(clean)
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
    processed=len(results); accepted=sum(x['status']=='accepted' for x in results)
    report={'schemaVersion':1,'season':a.season,'generatedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'gamesWithBox':processed,'gamesAccepted':accepted,'gamesExcluded':processed-accepted,
            'acceptanceRate':round(accepted/processed,4) if processed else 0,
            'cleanPossessions':len(included),'exclusionReasons':dict(reasons),
            'sample':results[:30], 'disclaimer':'Research-only, not approved as Portal player evaluations'}
    output=Path(a.output);audit=Path(a.audit);output.parent.mkdir(parents=True,exist_ok=True);audit.parent.mkdir(parents=True,exist_ok=True)
    audit.write_text(json.dumps(report,indent=2)+'\n')
    # Prevent public ratings when games are sparse or highly selected. Data stays audit-only in that case.
    if processed<20 or accepted<20 or len(included)<3000 or report['acceptanceRate']<.4:
        print('RAPM: quality/data gate not met; no ratings published. '+json.dumps({k:report[k] for k in ('gamesWithBox','gamesAccepted','cleanPossessions','acceptanceRate')}))
        return
    ratings=model_fit(included)
    payload={'schemaVersion':1,'season':a.season,'generatedAt':report['generatedAt'],
       'status':'experimental_not_approved_for_player_evaluations','dataSource':'ESPN via hoopR',
       'gamesAccepted':accepted,'gamesConsidered':processed,'cleanPossessions':len(included),
       'ridgeAlpha':1000,'unit':'points_per_100_possessions','ratings':ratings}
    output.write_text(json.dumps(payload,separators=(',',':'))+'\n')
    print(f'RAPM: wrote {len(ratings)} experimental player effects from {len(included)} possessions')

if __name__=='__main__':main()
