#!/usr/bin/env python3
"""Append-only calendar-day NIL stock prices to monthly public GitHub repository shards.

One price per ESPN ID and calendar day, overwritten only by a newer VALIDATED
score on the same day. Dated history never gets revised on later days.
The preseason anchor is immutable and separate from daily movements.
"""
import argparse,json,pathlib,datetime,math

MIN_PRICE,MAX_PRICE=20000,20000000

def is_price(n):
 return type(n) is int and MIN_PRICE<=n<=MAX_PRICE

def save(path,data):
 path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(data,separators=(',',':'),ensure_ascii=False)+'\n',encoding='utf-8')

def load(path):return json.loads(path.read_text(encoding='utf-8'))

def record(candidate,root,asof=None):
 payload=load(pathlib.Path(candidate));root=pathlib.Path(root)
 if payload.get('schemaVersion')!=1 or payload.get('model')!='NIL Estimation Model' or payload.get('season')!=2027 or payload.get('policyVersion')!=2:raise ValueError('Wrong pricing model/schema')
 entries=payload.get('byESPNId',{})
 if len(entries)<1000 or len(entries)!=payload.get('playerCount'):raise ValueError('Invalid scoring coverage')
 baseline_path=root/'preseason_2027.json';anchor=load(baseline_path)
 if anchor.get('schemaVersion')!=1 or anchor.get('season')!=2027 or len(anchor.get('byESPNId',{}))<1000:raise ValueError('Missing immutable preseason anchor')
 anchored=anchor['byESPNId']
 if len(set(anchored)&set(entries))<min(1000,int(len(anchored)*.8)):raise ValueError('Severe identity coverage loss')
 for id,v in entries.items():
  if not str(id).isdigit() or not is_price(v.get('value')):raise ValueError('Invalid ID/price')
  if id in anchored and v.get('preseason')!=anchored[id]:raise ValueError('Immutable preseason price changed for '+id)
 manifest_path=root/'manifest_2027.json';manifest=load(manifest_path)
 if manifest.get('schemaVersion')!=1 or manifest.get('season')!=2027:raise ValueError('Invalid history manifest')
 day=asof or str(payload.get('generatedAt',''))[:10]
 try:today=datetime.date.fromisoformat(day)
 except (ValueError,TypeError):raise ValueError('Invalid snapshot date')
 if day!=str(payload.get('generatedAt',''))[:10]:raise ValueError('Snapshot date differs from scored as-of')
 updated=sum(1 for row in entries.values() if row.get('status')=='UPDATED' and int(row.get('games') or 0)>0)
 if day<=anchor['asOf']:
  if updated:raise ValueError('Cannot record season evidence before/at frozen baseline date')
  print('Baseline date; no in-season stock snapshot written');return {'appended':False,'updated':0}
 if not updated:
  print('No actual current-season model evidence; no stock snapshot written');return {'appended':False,'updated':0}
 dates=manifest.get('dates') or []
 if dates and day<dates[-1]:raise ValueError('Historical snapshots cannot be backfilled or rewritten silently')
 month=day[:7];file=root/(month+'.json')
 shard=load(file) if file.exists() else {'schemaVersion':1,'season':2027,'month':month,'dates':[],'byESPNId':{}}
 if shard['season']!=2027 or shard['month']!=month:raise ValueError('Invalid month shard')
 sdates=shard['dates'];byid=shard['byESPNId'];new_date=day not in sdates
 if sdates and day<sdates[-1]:raise ValueError('Cannot rewrite past daily rows')
 if new_date:
  sdates.append(day)
  for vals in byid.values():vals.append(None)
 idx=len(sdates)-1
 for id,row in entries.items():
  vals=byid.get(id)
  if vals is None:vals=[None]*len(sdates);byid[id]=vals
  if len(vals)!=len(sdates):raise ValueError('Invalid monthly series length')
  vals[idx]=row['value']
 # Missing ID for this date stays null, rather than inheriting yesterday's value.
 for id,vals in byid.items():
  if len(vals)!=len(sdates):raise ValueError('Invalid monthly alignment')
 if new_date:
  if dates and day<=dates[-1]:raise ValueError('Manifest/shard disagree about latest date')
  manifest['dates'].append(day)
 if month not in manifest['months']:manifest['months'].append(month)
 if manifest['months']!=sorted(manifest['months']):raise ValueError('Unordered monthly shards')
 manifest['latestDate']=day
 manifest['baselineAsOf']=anchor['asOf']
 manifest['lastSourceGeneratedAt']=payload['generatedAt']
 # Validate entire candidate output BEFORE touching any durable file.
 if not all(isinstance(v,list) and len(v)==len(sdates) for v in byid.values()):raise ValueError('Bad history matrix')
 save(file,shard);save(manifest_path,manifest)
 print(f'History recorded {day}: {len(entries)} prices; {updated} current-season updates; monthly dates {len(sdates)}')
 return {'appended':True,'date':day,'count':len(entries),'updated':updated}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--new',required=True);p.add_argument('--root',default='published/stock_watch');p.add_argument('--as-of');a=p.parse_args();record(a.new,a.root,a.as_of)
