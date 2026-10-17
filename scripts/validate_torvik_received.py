#!/usr/bin/env python3
"""Validate Google Apps Script Torvik research feed and attach verified ESPN team IDs."""
import argparse
import datetime as dt
import json
import math
import re
from pathlib import Path
from torvik_bulk_daily import espn_crosswalk

SRC = 'https://barttorvik.com/2027_team_results.csv'

def validate(data):
    if not isinstance(data,dict) or data.get('schemaVersion')!=1 or data.get('season')!=2027:
        raise ValueError('Unexpected payload version or season')
    if data.get('sourceUrl')!=SRC:
        raise ValueError('Unexpected provider endpoint')
    if not re.fullmatch(r'[0-9a-f]{64}',str(data.get('sourceSha256',''))):
        raise ValueError('Invalid source digest')
    timestamp=dt.datetime.fromisoformat(data['retrievedAtUTC'].replace('Z','+00:00'))
    if timestamp.tzinfo is None:
        raise ValueError('Timestamp missing timezone')
    if timestamp>dt.datetime.now(dt.timezone.utc)+dt.timedelta(minutes=15):
        raise ValueError('Future data timestamp')
    if timestamp<dt.datetime.now(dt.timezone.utc)-dt.timedelta(days=30):
        raise ValueError('Unexpectedly old source timestamp')
    teams=data.get('teams')
    if not isinstance(teams,list) or not 340<=len(teams)<=400 or data.get('teamCount')!=len(teams):
        raise ValueError('Unexpected/partial team list')
    valid=[];names=set();ranks=set()
    for i,t in enumerate(teams):
        if not isinstance(t,dict):raise ValueError('Invalid team object')
        if not all(k in t for k in ['team','conf','record','rank','adjOE','adjDE','barthag','adjTempo']):
            raise ValueError('Missing required field in team '+str(i))
        name=t['team'];rank=t['rank']
        if not isinstance(name,str) or not name.strip() or not isinstance(t['conf'],str) or not t['conf'].strip():
            raise ValueError('Invalid school name or conference')
        if not isinstance(rank,int) or isinstance(rank,bool) or not 1<=rank<=400:
            raise ValueError('Invalid rank')
        if name in names or rank in ranks:raise ValueError('Duplicate school or rank')
        if not isinstance(t['record'],str) or not re.fullmatch(r'\d+-\d+',t['record']):
            raise ValueError('Invalid win-loss record')
        for k,lo,hi in [('adjOE',65,155),('adjDE',65,140),('barthag',0,1),('adjTempo',50,90)]:
            v=t[k]
            if isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v) or not lo<=v<=hi:
                raise ValueError('Invalid rating %s for %s'%(k,name))
        valid.append({'torvikTeam':name,'conference':t['conf'],'rank':rank,'record':t['record'],
            'adjOE':round(t['adjOE'],6),'adjDE':round(t['adjDE'],6),
            'adjEM':round(t['adjOE']-t['adjDE'],6),'barthag':round(t['barthag'],8),
            'adjTempo':round(t['adjTempo'],6),'espnTeamId':None})
        names.add(name);ranks.add(rank)
    stage='PRESEASON_PROJECTION' if all(x['record']=='0-0' for x in valid) else 'IN_SEASON_OR_FINAL'
    if data['ratingsStage']!=stage:
        raise ValueError('Incorrect preseason/in-season classification')
    return valid,stage

def run(source,context,output,qa):
    data=json.loads(Path(source).read_text())
    rows,stage=validate(data)
    mapped,unmatched,ambiguous,year=espn_crosswalk(rows,str(context),2027)
    # Apply ONLY historically verified exact Torvik-school-name -> ESPN-ID pairs.
    # This resolves schools such as FIU, NC State, UMKC, and cases where one
    # nickname is a prefix of multiple universities (Florida, Kansas).
    alias_path = Path('research_qa/torvik_verified_school_aliases_2026.json')
    if alias_path.is_file():
        historical = json.loads(alias_path.read_text())['schoolAliases']
        directory = json.loads(Path(context).read_text())['teams'][str(year)]
        teams_by_name = {r['torvikTeam']:r for r in rows}
        for name, eid in historical.items():
            if name not in teams_by_name or str(eid) not in directory:
                continue  # School absent this year or not yet in ESPN directory.
            teams_by_name[name]['espnTeamId'] = str(eid)
        ids=[r['espnTeamId'] for r in rows if r['espnTeamId']]
        if len(ids)!=len(set(ids)):
            raise ValueError('ESPN team-ID collision after applying verified school aliases')
        mapped=len(ids)
        unmatched=[r['torvikTeam'] for r in rows if not r['espnTeamId']]
        ambiguous=[x for x in ambiguous if x.get('team') in unmatched]
    if mapped < len(rows)*0.95:
        raise ValueError('Unsafe team-ID match rate %s/%s'%(mapped,len(rows)))
    doc={'schemaVersion':3,'season':2027,'source':'Bart Torvik published team-results CSV via Google Apps Script',
      'sourceUrl':SRC,'sourceSha256':data['sourceSha256'],
      'retrievedAtUTC':data['retrievedAtUTC'],'ratingsStage':stage,
      'teamCount':len(rows),'matchedESPNTeams':mapped,'crosswalkSourceSeason':int(year),
      'teams':sorted(rows,key=lambda r:r['rank'])}
    audit={'teamCount':len(rows),'matchedESPNTeams':mapped,'unmatched':unmatched,
           'ambiguous':ambiguous,'ratingsStage':stage,'sourceSha256':data['sourceSha256']}
    for dest,obj in [(output,doc),(qa,audit)]:
        p=Path(dest);p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(obj,indent=2)+'\n')
    print('Torvik research data validated: %s teams, %s matched ESPN IDs, %s unmatched, stage %s'
          %(len(rows),mapped,len(unmatched),stage))

if __name__=='__main__':
    a=argparse.ArgumentParser()
    a.add_argument('--input',default='research_qa/torvik_received_2027.json')
    a.add_argument('--context',default='public/research_team_context.json')
    a.add_argument('--output',default='research_qa/torvik_team_strength_2027_validated.json')
    a.add_argument('--qa',default='research_qa/torvik_team_strength_2027_received_qa.json')
    args=a.parse_args()
    run(args.input,args.context,args.output,args.qa)
