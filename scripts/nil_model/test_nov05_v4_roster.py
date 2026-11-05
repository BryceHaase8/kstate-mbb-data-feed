#!/usr/bin/env python3
import copy,json,pathlib,shutil,tempfile,sys
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/nil_model'))
import publish_guard,record_stock_history
load=lambda p:json.loads(pathlib.Path(p).read_text())
sw=ROOT/'public/stock_watch'
late=load(sw/'late_entrant_baselines_2027.json')
orig=load(sw/'preseason_2027.json')
v4=load(sw/'v4_preseason_2027_candidate.json')['byESPNId']
cur=load(ROOT/'public/nil_estimation_model_2027.json')
expected={'4433285':4539410,'5103628':202708,'5107508':2226515,'5125176':1204390,'5180837':665305,'5241932':123581,'5313437':44000,'5475372':41000}
assert orig['playerCount']==6057 and len(orig['byESPNId'])==6057
assert v4['5103628']==202708 and v4['5241932']==123581
assert orig['byESPNId']['5180837']==443145 and orig['byESPNId']['5313437']==50000
assert len(late['byESPNId'])==36
assert all(late['byESPNId'][pid]['value']==value for pid,value in expected.items() if pid in late['byESPNId'])
for pid in ('4433285','5107508','5125176','5180837','5313437'):
 entry=late['byESPNId'][pid];prev=cur['byESPNId'][pid]
 assert prev['preseason'] in (entry['sourcePreviouslyPublishedPreseason'],entry['value'])
assert len(set(expected)&set(cur['byESPNId']))>=7
new=copy.deepcopy(cur)
for pid,entry in late['byESPNId'].items():
 if entry['effectiveDate']>new['generatedAt'][:10]:continue
 value=entry['value'];row=new['byESPNId'].get(pid)
 if row:
  original=row['preseason'];ratio=row['value']/max(1,original)
  row['value']=max(20000,round(value*ratio)) if row.get('status')=='UPDATED' else value
  row['preseason']=value;row['anchorType']='LATE_ENTRANT_BASELINE_2027'
 else:
  new['byESPNId'][pid]={'value':value,'preseason':value,'currentOnly':None,'referenceOnly':None,
   'season':2027,'priorSeason':None,'games':0,'minutes':0,'weight':0,'roleWeight':0,
   'status':'PRESEASON_BASELINE','updateMethod':'PRESEASON_ONLY','evidenceGP':0,'evidenceMPG':0,
   'anchorType':'LATE_ENTRANT_BASELINE_2027'}
new['playerCount']=len(new['byESPNId'])
assert all(new['byESPNId'][pid]['preseason']==price for pid,price in expected.items())
with tempfile.TemporaryDirectory(prefix='nov05-v4-') as td:
 path=pathlib.Path(td)/'test-nil.json';path.write_text(json.dumps(new))
 publish_guard.check(str(path),str(ROOT/'public/nil_estimation_model_2027.json'),
  str(ROOT/'public/portal_factual_data.json'),anchor=str(sw/'preseason_2027.json'),
  late_entrants=str(sw/'late_entrant_baselines_2027.json'),
  opening_corrections=str(sw/'opening_price_corrections_2027.json'))
 stock=pathlib.Path(td)/'stock_watch';shutil.copytree(sw,stock)
 record_stock_history.record(path,stock)
print('PASS: eight V4-based ESPN-ID priors, preserved original 6057, publisher + stock history')
