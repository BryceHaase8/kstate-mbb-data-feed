#!/usr/bin/env python3
"""Immutable launch-baseline provenance: 3,051 V4 + 1,420 verified freshmen."""
import json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/'public'/'stock_watch'
def load(name):return json.loads((ROOT/name).read_text())
class RookiePreseasonChecks(unittest.TestCase):
 def test_composite_provenance_and_values(self):
  anchor=load('preseason_2027.json')
  old=load('preseason_2027_legacy_2026_10_24.json')
  v4=load('v4_preseason_2027_candidate.json')
  rookies=load('freshman_preseason_2027_candidate.json')
  manifest=load('manifest_2027.json')
  a=anchor['byESPNId'];v=v4['byESPNId'];r=rookies['byESPNId']
  self.assertEqual(len(v),3052);self.assertEqual(len(r),1420);self.assertEqual(len(a),4472)
  self.assertEqual(set(old['byESPNId']),set(v)-{'5281366'})
  self.assertEqual(v['5281366'],791196)
  self.assertFalse(set(v)&set(r))
  self.assertEqual(set(a),set(v)|set(r))
  self.assertEqual({**v,**r},a)
  self.assertTrue(all(type(price)==int and 20000<=price<=20000000 for price in a.values()))
  self.assertEqual(anchor['composition']['originalV4'],3052)
  self.assertEqual(anchor['composition']['originalRookie'],1420)
  self.assertEqual(rookies['audit']['rankAmbiguous'],0)
  self.assertEqual(rookies['audit']['disjointHistorical'],0)
  self.assertEqual(r['5142731'],3300000)
  self.assertEqual(r['5144523'],1576600)
  self.assertEqual(manifest['baselinePlayerCount'],4472)
  self.assertEqual(manifest['baselineAsOf'],anchor['asOf'])
  self.assertEqual(manifest['baselineVersion'],anchor['baselineVersion'])
  self.assertFalse(manifest['dates'])
  self.assertFalse(manifest['months'])
if __name__=='__main__':unittest.main()
