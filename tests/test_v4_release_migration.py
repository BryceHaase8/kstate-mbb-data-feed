#!/usr/bin/env python3
"""Synthetic release check: exact ESPN-ID V4 + disjoint HS freshmen migration."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'/'nil_model'))
from publish_guard import check

class ReleaseMigrationTests(unittest.TestCase):
 def test_verified_migration_and_unsafe_cases(self):
  v4ids=[str(4000000+k) for k in range(3051)]
  kids=[str(6000000+k) for k in range(1420)]
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   def store(name,obj):
    file=root/(name+'.json');file.write_text(json.dumps(obj));return str(file)
   old_prices={p:100000 for p in v4ids}
   v4_prices={p:150000 for p in v4ids}
   v4_prices['5281366']=791196
   rookie_prices={p:80000 for p in kids}
   b={'schemaVersion':1,'season':2027,'playerCount':3051,'asOf':'2026-10-24','byESPNId':old_prices}
   v={'schemaVersion':1,'season':2027,'playerCount':3052,'baselineVersion':'V4_FROZEN_SITE_V771_3052_2026_10_27','byESPNId':v4_prices}
   q={'schemaVersion':1,'season':2027,'playerCount':1420,'baselineVersion':'ROOKIE_HS_SITE_V771_ESPN_ID_2026_10_27','byESPNId':rookie_prices}
   a={'schemaVersion':1,'season':2027,'playerCount':4472,'asOf':'2026-10-27',
      'baselineVersion':'V4_FROZEN_SITE_V771_3052_PLUS_FRESHMEN_2026_10_27',
      'byESPNId':{**v4_prices,**rookie_prices}}
   previous={'season':2027,'policyVersion':2,'byESPNId':{p:{'preseason':100000,'value':100000} for p in v4ids}}
   now={'season':2027,'policyVersion':3,'generatedAt':'2026-10-27T00:00:00Z',
     'factualGeneratedAt':'2026-10-26T00:00:00Z',
     'byESPNId':{p:{'preseason':price,'value':price,'status':'PRESEASON_BASELINE'}
                 for p,price in a['byESPNId'].items()}}
   facts={'generatedAt':'2026-10-26T00:00:00Z','latestSeason':2026}
   history={'baselineAsOf':'2026-10-27','dates':[],'months':[]}
   table={'new':now,'old':previous,'source':facts,'anchor':a,
     'legacy':b,'history':history,'rookies':q,'v4':v}
   paths={name:store(name,obj) for name,obj in table.items()}
   def run():return check(*(paths[x] for x in ('new','old','source','anchor','legacy','history','rookies','v4')))
   self.assertTrue(run())
   def invalid(name,field,updated):
    item=copy.deepcopy(table[name]);item[field]=updated
    paths[name]=store(name,item)
    with self.assertRaises(ValueError):run()
    paths[name]=store(name,table[name])
   bad=copy.deepcopy(now);bad['byESPNId'][kids[5]]['preseason']=40000
   paths['new']=store('new',bad)
   with self.assertRaises(ValueError):run()
   paths['new']=store('new',now)
   invalid('history','dates',['2026-10-28'])
   invalid('source','latestSeason',2027)
   bad=copy.deepcopy(q);bad['byESPNId'][kids[2]]=92000
   paths['rookies']=store('rookies',bad)
   with self.assertRaises(ValueError):run()
   paths['rookies']=store('rookies',q)
   bad=copy.deepcopy(q);bad['byESPNId'][kids[0]]=80000
   bad['byESPNId'][v4ids[10]]=60000;del bad['byESPNId'][kids[1]]
   paths['rookies']=store('rookies',bad)
   with self.assertRaises(ValueError):run()
if __name__=='__main__':unittest.main()
