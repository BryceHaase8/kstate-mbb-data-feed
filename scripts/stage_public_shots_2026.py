#!/usr/bin/env python3
"""Research only: ESPN 2025-26 shots, mapped to verified D-I games & athlete IDs.
No staff data, no Netlify, no production push, no third-party lineup assumptions.
"""
import urllib.request,json,gzip,csv,math
from pathlib import Path
from collections import defaultdict,Counter
import pandas as pd
base=Path('research_data/staged')
out=base/'portal_shots_2026'
out.mkdir(parents=True,exist_ok=True)
p=Path('/tmp/shots_2026.parquet')
url='https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_mens_college_basketball_shots/shots_2026.parquet'
if not p.exists():
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Portal-Research/1.0'}),timeout=120) as r:p.write_bytes(r.read())
assert p.stat().st_size>10000000
with gzip.open('research_data/historical/season_totals/player_season_2026.csv.gz','rt',encoding='utf8') as f:season=list(csv.DictReader(f))
names={str(r['team_id']):r['team_name'] for r in season if r.get('team_id') and r.get('team_name')}
positions={str(r['athlete_id']):str(r.get('position') or '') for r in season}
d1=set(names)
assert len(d1)==365,len(d1)
opps={}
for i in range(64):
    j=json.loads((base/'portal_team_schedules'/f'teams_{i:02d}.json').read_text())
    for k,events in j['teams'].items():
        year,tid=k.split(':')
        if year!='2026' or tid not in d1:continue
        for ev in events:
            other=str(ev[4] or '')
            if other in d1 and other!=tid:opps[(str(ev[1]),tid)]=other
assert len(opps)>9500,len(opps)
d=pd.read_parquet(p)
assert len(d)==991836 and set(['coordinate_x','coordinate_y','score_value','scoring_play','athlete_id_1']).issubset(d.columns)
d=d[d.type_text.isin(['JumpShot','LayUpShot','DunkShot','TipShot','Shot'])]
shards=[defaultdict(list) for _ in range(128)]
counts=Counter();seen_games=set();seen_teams=set()
arc=22+1.75/12; corner=21+7.875/12;cy_join=5.25+math.sqrt(arc*arc-corner*corner)
for r in d.itertuples(index=False):
    counts['allFieldGoals']+=1
    if pd.isna(r.athlete_id_1) or pd.isna(r.team_id) or pd.isna(r.game_id):counts['noIdentity']+=1;continue
    aid=str(int(r.athlete_id_1));tid=str(int(r.team_id));game=str(int(r.game_id))
    other=opps.get((game,tid))
    if other is None:counts['notD1vsD1']+=1;continue
    val=int(r.score_value) if pd.notna(r.score_value) else 0
    if val not in (2,3):counts['invalidValue']+=1;continue
    counts['d1Fga']+=1
    x,y=r.coordinate_x,r.coordinate_y
    if pd.isna(x) or pd.isna(y) or not(-47.5<=x<=47.5 and -25.5<=y<=25.5):counts['invalidCoords']+=1;continue
    court_x=float(-y if x<0 else y);court_y=float(47-abs(x))
    if not(-25.5<=court_x<=25.5 and 0<=court_y<=47.5):counts['invalidTransform']+=1;continue
    distance=math.hypot(abs(x)-41.75,y)
    if val==3:zone='Deep 3' if distance>=26 else 'Corner 3' if court_y<=cy_join+1.2 and abs(court_x)>=corner-1 else 'Above Break 3'
    else:zone='Rim' if distance<5 else 'Short Paint' if distance<8 else 'Midrange'
    made=1 if r.scoring_play is True or str(r.scoring_play).lower()=='true' else 0
    ass=str(int(r.athlete_id_2)) if made and pd.notna(r.athlete_id_2) else None
    shards[int(aid)%128][aid].append([game,tid,other,val,made,round(court_x,2),round(court_y,2),ass,zone])
    counts['mappedFga']+=1
    seen_games.add(game);seen_teams.add(tid)
athletes=sum(map(len,shards))
coverage=counts['mappedFga']/max(counts['d1Fga'],1)
print('COVERAGE',dict(counts),'games',len(seen_games),'teams',len(seen_teams),'athletes',athletes,'coordinateShare',coverage)
assert counts['mappedFga']>400000,counts
assert len(seen_games)>4500 and len(seen_teams)>=350 and athletes>3800
def group(p):
    p=p.strip().upper()
    if p in ('G','PG','SG','CG'):return 'guards'
    if p in ('F','SF','PF','G/F','F/G','WING'):return 'forwards'
    if p in ('C','PF/C','F/C'):return 'bigs'
    return None
by_group=defaultdict(list)
for sh in shards:
    for aid,events in sh.items():
        g=group(positions.get(aid,''))
        if g:by_group[g].append(events)
peers={};diets={}
for grp,players in by_group.items():
    qualified=[events for events in players if len(events)>=100]
    if len(qualified)<50:qualified=[events for events in players if len(events)>=50]
    if not qualified:continue
    zp={}
    for z in ('Rim','Short Paint','Midrange','Corner 3','Above Break 3','Deep 3'):
        samples=[r for e in qualified for r in e if r[8]==z]
        zp[z]={'fgPct':round(100*sum(r[4] for r in samples)/len(samples),2) if samples else None}
    peers[grp]=zp
    share=defaultdict(list)
    for events in qualified:
        counts2=Counter('3PT' if r[3]==3 else 'Rim' if r[8]=='Rim' else 'Paint' if r[8]=='Short Paint' else 'Midrange' for r in events)
        for z in ('Rim','Paint','Midrange','3PT'):share[z].append(100*counts2[z]/len(events))
    diets[grp]={z:round(sum(a)/len(a),2) for z,a in share.items()}
for i,sh in enumerate(shards):
    for events in sh.values():events.sort(key=lambda r:(r[0],r[5],r[6]))
    doc={'schemaVersion':1,'season':2026,'shard':i,'modulo':128,'fields':['gameId','teamId','opponentId','shotValue','made','courtX','courtY','assistId','zone'],'players':sh}
    (out/f'shots_{i:03d}.json').write_text(json.dumps(doc,separators=(',',':')))
complete=coverage>=.96 and len(seen_teams)>=355 and len(seen_games)>=4800 and athletes>=4000
manifest={'schemaVersion':1,'season':2026,'seasonLabel':'2025-26','modulo':128,'available':True,'complete':complete,
          'source':'Published SportsDataverse ESPN shots_2026.parquet; exact D-I matchup and player ID',
          'teams':names,'peers':peers,'peerShotDiet':diets,
          'metrics':{'nationalSourceFG':len(d),'d1FGA':counts['d1Fga'],'mappedFGA':counts['mappedFga'],'mappedCoverage':round(coverage,4),'games':len(seen_games),'teams':len(seen_teams),'athletes':athletes}}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2))
assert sum(len(v) for sh in shards for v in sh.values())==counts['mappedFga']
print('RESULT',json.dumps({'complete':complete,'metrics':manifest['metrics'],'peerGroups':list(peers)}))
