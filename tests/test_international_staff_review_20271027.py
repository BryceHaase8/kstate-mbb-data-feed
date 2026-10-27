#!/usr/bin/env python3
"""Exact-ESPN-ID review of staff-approved 2026-27 preseason international anchors."""
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def load(path):
 return json.loads((ROOT/path).read_text(encoding="utf-8"))

class InternationalStaffReviewTests(unittest.TestCase):
 def test_staff_16_immutable_rebase(self):
  old=load("public/stock_watch/preseason_2027_before_staff_20261027.json")
  new=load("public/stock_watch/preseason_2027.json")
  edited=load("public/stock_watch/international_top100_staff_review_20271027.json")
  staff12=load("public/stock_watch/international_pro_2027_market_priors.json")["byESPNId"]
  research22=load("public/stock_watch/international_top100_noncollege_2027_priors.json")["byESPNId"]
  prices=edited["byESPNId"]
  before=old["byESPNId"]
  after=new["byESPNId"]
  self.assertEqual(edited["playerCount"],len(prices))
  self.assertEqual(len(prices),16)
  self.assertEqual(set(prices),set(edited["sourceBaselineByESPNId"]))
  self.assertEqual(old["playerCount"],new["playerCount"])
  self.assertEqual(len(before),len(after))
  self.assertEqual(len(before),6057)
  self.assertEqual(set(before),set(after))
  self.assertEqual({pid for pid in before if before[pid]!=after[pid]},set(prices))
  self.assertEqual(after,{**before,**prices})
  self.assertEqual(edited["sourceBaselineByESPNId"],{pid:before[pid] for pid in prices})
  self.assertEqual(sum(prices.values())-sum(edited["sourceBaselineByESPNId"].values()),9447500)
  self.assertFalse(set(prices)&set(staff12))
  for pid,val in staff12.items():self.assertEqual(after[pid],val)
  for pid,val in research22.items():
   if pid not in prices:self.assertEqual(after[pid],val)
  self.assertEqual(new["composition"]["internationalStaffReviewed"],16)
  self.assertEqual(new["baselineVersion"],old["baselineVersion"]+"_STAFF_REVIEW_16")
  self.assertEqual(prices["5312303"],250000)
  self.assertEqual(edited["priorCollegeException"]["espnId"],"5312303")
  self.assertEqual(len(edited["reviewedRows"]),16)
  self.assertTrue(all(x["espnId"] in prices and x["source"]=="STAFF_EDITED_GOOGLE_SHEET"
                      for x in edited["reviewedRows"]))

 def test_stock_watch_is_zero(self):
  a=load("public/stock_watch/preseason_2027.json")
  manifest=load("public/stock_watch/manifest_2027.json")
  self.assertEqual(manifest["baselineVersion"],a["baselineVersion"])
  self.assertEqual(manifest["baselinePlayerCount"],6057)
  self.assertFalse(manifest["dates"])
  self.assertFalse(manifest["months"])
  self.assertEqual(manifest["staffInternationalReview"]["count"],16)

if __name__=="__main__":unittest.main()
