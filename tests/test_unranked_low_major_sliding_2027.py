#!/usr/bin/env python3
"""Unranked / low-major ESPN-ID NIL opening audit, no outside runtime dependency."""
import json, unittest
from pathlib import Path

R=Path(__file__).resolve().parents[1]
def load(path):return json.loads((R/path).read_text())
def curve(rank):return int(round((5000+45000*((365-rank)/364)**1.35)/100)*100)

class SlidingScalePreseason2027(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.rollback=load('public/stock_watch/preseason_2027_before_unranked_sliding_20261027.json')
  cls.final=load('public/stock_watch/preseason_2027.json')
  cls.overlay=load('public/stock_watch/unranked_low_major_sliding_2027_priors.json')
  cls.freshman=load('public/stock_watch/freshman_preseason_2027_candidate.json')
  cls.other=load('public/stock_watch/roster_other_preseason_2027_candidate.json')
  cls.roster=load('data/roster_2027_advanced.json')
  cls.ranks=load('research_qa/torvik_2027_unranked_preseason_rank_lock.json')
  cls.manifest=load('public/stock_watch/manifest_2027.json')
 def test_exact_cohort_and_no_unapproved_identity_movement(self):
  a=self.rollback['byESPNId'];b=self.final['byESPNId'];q=self.overlay
  self.assertEqual(len(a),len(b));self.assertEqual(len(a),6057)
  self.assertEqual(q['playerCount'],1835)
  self.assertEqual(set(q['byESPNId']),set(q['previousByESPNId']))
  self.assertEqual(set(q['byESPNId']),set(q['provenanceByESPNId']))
  self.assertEqual(set(q['byESPNId']),set(q['teamRankByESPNId']))
  self.assertEqual(b,{**a,**q['byESPNId']})
  self.assertEqual({p for p in a if a[p]!=b[p]},set(q['byESPNId']))
  self.assertEqual(q['previousByESPNId'],{p:a[p] for p in q['byESPNId']})
  self.assertEqual(q['methodCounts']['UNRANKED_SCHOOL_PRIOR_2026'],1044)
  self.assertEqual(q['methodCounts']['SITE_UNMODELED_PROVISIONAL_50000'],791)
  self.assertEqual(sum(q['byESPNId'].values())-sum(q['previousByESPNId'].values()),-47633500)
  self.assertEqual(self.final['composition']['unrankedSliding2027'],1835)
 def test_rank_provenance_and_scale_for_every_identity(self):
  players={p[0]:p for p in self.roster['players']}
  strength=self.ranks['byESPNTeamId'];q=self.overlay
  self.assertEqual(len(strength),365)
  for pid,p in q['byESPNId'].items():
   teamid=players[pid][2]
   rank=strength[teamid]['rank']
   self.assertEqual(q['teamRankByESPNId'][pid],rank,pid)
   self.assertEqual(p,curve(rank),pid)
   self.assertTrue(5000<=p<=50000)
   origin=q['provenanceByESPNId'][pid]
   if origin=='UNRANKED_SCHOOL_PRIOR_2026':
    self.assertEqual(self.freshman['methodByESPNId'][pid],origin)
   elif origin=='SITE_UNMODELED_PROVISIONAL_50000':
    self.assertEqual(self.other['methodByESPNId'][pid],origin)
    self.assertEqual(q['previousByESPNId'][pid],50000)
   else: self.fail('Unexpected source for '+pid)
 def test_protected_ranked_v4_and_international_unmodified(self):
  protection=set()
  for filename in ['public/stock_watch/international_pro_2027_market_priors.json',
                   'public/stock_watch/international_top100_noncollege_2027_priors.json',
                   'public/stock_watch/international_top100_staff_review_20271027.json']:
   protection.update(load(filename)['byESPNId'])
  protection.update(p for p,m in self.freshman['methodByESPNId'].items() if m=='RANKED_HS_2026_27')
  protection.update(load('public/stock_watch/v4_preseason_2027_candidate.json')['byESPNId'])
  protection.update(p for p,m in self.other['methodByESPNId'].items() if m=='LEGACY_MODEL_PRESEASON_PRESERVED')
  self.assertFalse(set(self.overlay['byESPNId'])&protection)
  a=self.rollback['byESPNId'];b=self.final['byESPNId']
  self.assertTrue(all(a[p]==b[p] for p in protection))
 def test_team_economics_better_at_the_bottom(self):
  rows={p[0]:p for p in self.roster['players']}
  groups={}
  for row in self.roster['players']:groups.setdefault(row[2],[]).append(row[0])
  old=self.rollback['byESPNId'];new=self.final['byESPNId']
  for id,expected_before,expected_after in [
   ('2379',733096,283096),('2400',529167,168867),('2697',909778,414778)]:
   pids=groups[id]
   self.assertEqual(sum(old.get(p,0) for p in pids),expected_before)
   self.assertEqual(sum(new.get(p,0) for p in pids),expected_after)
  self.assertEqual(curve(1),50000);self.assertEqual(curve(365),5000)
  self.assertLess(curve(300),10000)
  self.assertGreater(curve(10),48000)
 def test_no_stock_watch_history_and_floor(self):
  self.assertFalse(self.manifest['dates'])
  self.assertFalse(self.manifest['months'])
  self.assertEqual(self.manifest['baselineVersion'],self.final['baselineVersion'])
  self.assertEqual(self.manifest['unrankedRankSliding']['count'],1835)
  self.assertEqual(min(self.overlay['byESPNId'].values()),5000)

if __name__=='__main__': unittest.main()
