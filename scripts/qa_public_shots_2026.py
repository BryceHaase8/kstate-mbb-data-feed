#!/usr/bin/env python3
"""Research QA: real 2025-26 D-I shot attempts against archived player-game box FGA."""
import gzip,csv,json
from pathlib import Path
from collections import Counter
root=Path('research_data/staged')
folder=root/'portal_shots_2026'
manifest=json.loads((folder/'manifest.json').read_text())
shots=Counter()
for i in range(128):
    j=json.loads((folder/f'shots_{i:03d}.json').read_text())
    for aid,events in j['players'].items():
        for x in events:shots[(str(x[0]),str(x[1]),aid)]+=1
assert sum(shots.values())==manifest['metrics']['mappedFGA']
matchups=set()
for i in range(64):
    x=json.loads((root/'portal_team_schedules'/f'teams_{i:02d}.json').read_text())
    for key,rows in x['teams'].items():
        if not key.startswith('2026:'):continue
        tid=key.split(':')[1]
        for r in rows:
            if str(r[4] or '') in manifest['teams']:matchups.add((str(r[1]),tid))
box=Counter()
with gzip.open('research_data/historical/game_logs/player_game_logs_2026.csv.gz','rt',encoding='utf8') as f:
    for row in csv.DictReader(f):
        if (row['game_id'],row['team_id']) not in matchups:continue
        box[(row['game_id'],row['team_id'],row['athlete_id'])]+=float(row.get('fga') or 0)
matched=set(box)&set(shots)
issues=sorted([(k,box[k],shots[k]) for k in matched if box[k]!=shots[k]],key=lambda a:abs(a[1]-a[2]),reverse=True)
report={'season':2026,'boxFGA':sum(box.values()),'shotFGA':sum(shots.values()),
        'ratioShotsToBox':round(sum(shots.values())/max(1,sum(box.values())),6),
        'commonPlayerGameKeys':len(matched),
        'exactPlayerGameMatches':len(matched)-len(issues),
        'exactMatchShare':round((len(matched)-len(issues))/max(1,len(matched)),6),
        'boxFgaNoShotRows':sum(v for k,v in box.items() if k not in shots),
        'shotFgaNoBoxRows':sum(v for k,v in shots.items() if k not in box),
        'largestDiscrepancies':issues[:12]}
print('RECONCILIATION',json.dumps(report,indent=2))
Path('research_qa/shot_charts').mkdir(parents=True,exist_ok=True)
Path('research_qa/shot_charts/box_vs_shot_2026.json').write_text(json.dumps(report,indent=2))
assert .94<=report['ratioShotsToBox']<=1.06,report
