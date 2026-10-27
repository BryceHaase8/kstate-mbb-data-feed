#!/usr/bin/env python3
"""Synthetic test: one and only one V4 baseline migration, no private labels."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'/'nil_model'))
from publish_guard import check

class ReleaseMigrationTests(unittest.TestCase):
 def test_verified_migration_and_unsafe_cases(self):
  ids=[str(4000000+k) for k in range(3051)]
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   def store(name,x):
    p=root/name;p.write_text(json.dumps(x));return str(p)
   old_prices={id:100000 for id in ids}
   new_prices={id:150000 for id in ids}
   original={'schemaVersion':1,'season':2027,'playerCount':3051,'asOf':'2026-10-24','byESPNId':old_prices}
   frozen={'schemaVersion':1,'season':2027,'playerCount':3051,'asOf':'2026-10-27','baselineVersion':'V4_FROZEN_SITE_V770_2026_10_27','byESPNId':new_prices}
   previous={'season':2027,'policyVersion':2,'byESPNId':{id:{'preseason':100000,'value':100000} for id in ids}}
   ready={'season':2027,'policyVersion':3,'generatedAt':'2026-10-27T00:00:00Z','factualGeneratedAt':'2026-10-26T00:00:00Z',
          'byESPNId':{id:{'preseason':150000,'value':150000,'status':'PRESEASON_BASELINE'} for id in ids}}
   facts={'generatedAt':'2026-10-26T00:00:00Z','latestSeason':2026}
   history={'schemaVersion':1,'season':2027,'baselineAsOf':'2026-10-27','dates':[],'months':[]}
   paths={name:store(name+'.json',x) for name,x in [('old',previous),('new',ready),('source',facts),('anchor',frozen),('legacy',original),('history',history)]}
   def run():return check(paths['new'],paths['old'],paths['source'],paths['anchor'],paths['legacy'],paths['history'])
   self.assertTrue(run())
   changed=copy.deepcopy(ready);changed['byESPNId'][ids[42]]['preseason']=200000
   paths['new']=store('new.json',changed)
   with self.assertRaises(ValueError):run()
   paths['new']=store('new.json',ready)
   changed=copy.deepcopy(history);changed['dates']=['2026-11-02'];changed['months']=['2026-11']
   paths['history']=store('history.json',changed)
   with self.assertRaises(ValueError):run()
   paths['history']=store('history.json',history)
   changed=copy.deepcopy(facts);changed['latestSeason']=2027
   paths['source']=store('source.json',changed)
   with self.assertRaises(ValueError):run()
if __name__=='__main__':unittest.main()
