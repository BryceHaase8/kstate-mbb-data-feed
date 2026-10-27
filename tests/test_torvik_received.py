#!/usr/bin/env python3
"""Tests Google Apps Script reduced ratings payload and unambiguous ESPN ID join. No network."""
import copy,datetime as dt,json,tempfile,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from validate_torvik_received import validate,run

def sample(n=365):
    teams=[]
    for k in range(n):
        name='Kansas St.' if k==9 else 'West Florida' if k==10 else 'Mock University %d'%k
        teams.append({'team':name,'conf':'B12' if k==9 else 'MVC',
            'rank':k+1,'record':'0-0','adjOE':110.0,'adjDE':100.0,
            'barthag':0.7,'adjTempo':70.0})
    return {'schemaVersion':1,'season':2027,
      'sourceUrl':'https://barttorvik.com/2027_team_results.csv',
      'sourceSha256':'a'*64,'retrievedAtUTC':dt.datetime.now(dt.timezone.utc).isoformat(),
      'teamCount':n,'ratingsStage':'PRESEASON_PROJECTION','teams':teams}

fixture=sample()
rows,stage=validate(fixture)
assert len(rows)==365 and stage=='PRESEASON_PROJECTION'
for name,mutation in [
 ('missing team',lambda d:d['teams'].pop()),
 ('wrong year',lambda d:d.update(season=2026)),
 ('duplicate team',lambda d:d['teams'][1].update(team=d['teams'][0]['team'])),
 ('bad efficiency',lambda d:d['teams'][1].update(adjDE=999)),
 ('wrong stage',lambda d:d.update(ratingsStage='IN_SEASON_OR_FINAL'))
]:
    bad=copy.deepcopy(fixture)
    mutation(bad)
    try:validate(bad)
    except ValueError:pass
    else:raise AssertionError('Failed to reject '+name)

with tempfile.TemporaryDirectory() as tmp:
    base=Path(tmp)
    context={'teams':{'2026':{}}}
    for i,team in enumerate(fixture['teams']):
        if team['team']=='West Florida':continue  # No 2025-26 D-I ESPN context
        context['teams']['2026'][eid]={'name':'Kansas State Wildcats' if eid=='2306' else team['team']+' Wildcats'}
    (base/'context.json').write_text(json.dumps(context))
    (base/'input.json').write_text(json.dumps(fixture))
    run(base/'input.json',base/'context.json',base/'result.json',base/'audit.json')
    output=json.loads((base/'result.json').read_text())
    assert output['matchedESPNTeams']==365
    assert next(x for x in output['teams'] if x['torvikTeam']=='Kansas St.')['espnTeamId']=='2306'
    assert next(x for x in output['teams'] if x['torvikTeam']=='West Florida')['espnTeamId']=='2697'
    assert output['ratingsStage']=='PRESEASON_PROJECTION'
print('PASS: payload validation, corruption rejection, and Torvik-to-ESPN ID crosswalk')
