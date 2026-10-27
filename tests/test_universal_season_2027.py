#!/usr/bin/env python3
"""Policy-level 2026-27 season scoring tests: all player groups."""
import math
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'/'nil_model'))
from cold_start import cold_start_reference,cold_start_relative_update
from nil_season_engine import player_weight,cold_start_weight,stabilized_virtual_season,past_seasons

def observed(games,mpg,pts30=16,three_pct=.35,position='G'):
 minutes=games*mpg
 p3=5.0*minutes/30;p2=8.0*minutes/30
 z={'season':2027,'gp':games,'gs':games,'minutes':minutes,'mpg':mpg,
    'teamId':'2306','position':position,'two_pa':p2,'three_pa':p3,
    'two_pm':p2*.54,'three_pm':p3*three_pct,'fta':3*minutes/30,
    'ftm':2.2*minutes/30,'reb':5*minutes/30,'ast':4*minutes/30,
    'stl':minutes/30,'blk':.4*minutes/30,'pf':2*minutes/30,
    'tov':1.7*minutes/30,'oreb':1.1*minutes/30,'dreb':3.9*minutes/30}
 z['fga']=z['two_pa']+z['three_pa'];z['fgm']=z['two_pm']+z['three_pm']
 z['pts']=2*z['two_pm']+3*z['three_pm']+z['ftm']
 z['ppg']=z['pts']/games;z['rpg']=z['reb']/games;z['apg']=z['ast']/games
 return z

class UniversalSeasonTests(unittest.TestCase):
 def test_references_are_explicit_expected_college_profiles_not_espring_history(self):
  prices=[50000,200000,750000,2500000,3500000]
  ref=[cold_start_reference(price,'G',2027,'2306') for price in prices]
  self.assertTrue(all(x['season']==2027 and x['gp']==30 for x in ref))
  self.assertTrue(all(x['fga']>0 and x['two_pa']+x['three_pa']==x['fga'] for x in ref))
  self.assertTrue(all(.35<x['ts_pct']<.75 for x in ref))
  self.assertEqual([r['teamId'] for r in ref],['2306']*len(ref))
  self.assertEqual(past_seasons({'seasons':[ref[0]]},2027),[])
  self.assertEqual(past_seasons({'seasons':[ref[0]]},2028),[ref[0]])
  self.assertTrue(all(x['mpg']<y['mpg'] for x,y in zip(ref,ref[1:])))
  self.assertGreater(cold_start_reference(150000,'C',2027,'2306')['reb'],ref[0]['reb'])

 def test_same_model_reference_preserves_staff_dollars(self):
  for base in [50000,250000,900000,3500000]:
   for weight in [0,.02,.5,.91]:
    self.assertEqual(cold_start_relative_update(base,400000,400000,weight),base)
    self.assertEqual(cold_start_relative_update(base,500000,500000,weight),base)

 def test_evidence_moves_every_cold_start_up_or_down(self):
  for base in [50000,250000,900000,3500000]:
   w1=cold_start_weight(1,30)[0]
   w10=cold_start_weight(10,300)[0]
   w30=cold_start_weight(30,900)[0]
   self.assertTrue(0<w1<w10<w30<1)
   self.assertTrue(.90<w30<.93)
   upside=[cold_start_relative_update(base,1000000,500000,w) for w in (w1,w10,w30)]
   down=[cold_start_relative_update(base,250000,500000,w) for w in (w1,w10,w30)]
   self.assertTrue(base<=upside[0]<upside[1]<upside[2])
   self.assertTrue(base>=down[0]>down[1]>down[2])

 def test_one_hot_game_does_not_override_price(self):
  w=cold_start_weight(1,30)[0]
  for base in [50000,3500000]:
   p=cold_start_relative_update(base,50_000_000,50000,w)
   self.assertLess(p/base,1.06)
  late=cold_start_weight(30,900)[0]
  self.assertLessEqual(cold_start_relative_update(3500000,20_000_000,20000,late),20_000_000)
  self.assertLessEqual(cold_start_relative_update(50000,20_000_000,20000,late),400000)

 def test_low_mpg_updates_but_lower_confidence(self):
  fast=cold_start_weight(30,900)[0]
  slow=cold_start_weight(30,180)[0]
  self.assertTrue(.7<slow<fast)
  self.assertNotEqual(cold_start_relative_update(900000,600000,500000,slow),900000)

 def test_virtual_comparison_uses_proper_observations(self):
  ref=cold_start_reference(800000,'G',2027,'2306')
  for gp,mpg in [(1,30),(10,30),(30,30),(30,6)]:
   cur=observed(gp,mpg)
   virtual,role_weight=stabilized_virtual_season(cur,ref,2027)
   self.assertTrue(0<role_weight<1)
   self.assertEqual(virtual['season'],2027)
   self.assertEqual(virtual['gp'],30)
   self.assertEqual(virtual['teamId'],'2306')
   self.assertEqual(virtual['fga'],virtual['two_pa']+virtual['three_pa'])
   self.assertEqual(virtual['fgm'],virtual['two_pm']+virtual['three_pm'])
   self.assertEqual(virtual['rpg'],virtual['reb']/30)
   self.assertTrue(0<virtual['mpg']<40)

 def test_invalid_reference_and_evidence_fail_closed(self):
  for amount in [0,19999,20000001,float('nan')]:
   with self.assertRaises(ValueError):cold_start_reference(amount,'G',2027,'2306')
  for nums in [(0,1,1,.3),(100000,0,1,.3),(100000,1,0,.3),
               (100000,1,1,-.01),(100000,1,1,1)]:
   with self.assertRaises(ValueError):cold_start_relative_update(*nums)

if __name__=='__main__':unittest.main()
