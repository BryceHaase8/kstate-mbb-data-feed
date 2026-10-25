#!/usr/bin/env python3
"""Conservative national publish drift / as-of policy; independent of model."""
import argparse,json,pathlib,datetime,math,statistics

def check(new,old,source):
 n=json.loads(pathlib.Path(new).read_text())
 o=json.loads(pathlib.Path(old).read_text())
 f=json.loads(pathlib.Path(source).read_text())
 assert n['season']==2027 and n['policyVersion']==2
 assert n['factualGeneratedAt']==f['generatedAt']
 assert int(f.get('latestSeason') or 0)<=2027
 rows=n['byESPNId'];older=o['byESPNId']
 common=set(rows)&set(older)
 assert len(common)>=(min(2700,int(.90*len(older)))), 'Major athlete-ID loss'
 assert len(rows)>=int(.90*len(older)), 'National price feed lost too many players'
 # The game source must not have future dates or fabricated timestamps.
 asof=datetime.date.fromisoformat(n['generatedAt'][:10]);stamp=datetime.date.fromisoformat(f['generatedAt'][:10]);assert stamp<=asof
 current=sum(1 for r in rows.values() if r['status']=='UPDATED')
 if int(f.get('latestSeason') or 0)<2027:
  assert not current, 'Preseason feed should not invent current-season prices'
  assert all(rows[k]['value']==older[k]['value'] for k in common), 'Preseason prices changed without new games'
 shifts=[abs(math.log(rows[k]['value']/older[k]['value'])) for k in common]
 median=statistics.median(shifts)
 assert median<.12, f'National median day-to-day price shift {median:.3f} above 12%'
 very_large=sum(1 for x in shifts if x>math.log(4))
 assert very_large<=max(6,int(len(common)*.005)), f'{very_large} players moved 4x in one publish'
 assert len(rows)<=20000
 print(json.dumps({'players':len(rows),'shared':len(common),'updated':current,'median_abs_log_change':round(median,4),'over_4x':very_large}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--new',required=True);p.add_argument('--old',required=True);p.add_argument('--source',required=True);a=p.parse_args();check(a.new,a.old,a.source)
