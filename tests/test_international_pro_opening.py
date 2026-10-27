#!/usr/bin/env python3
"""Exact-ID reviewed 2027 professional-import opening NIL prior checks."""
import json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/"public/stock_watch"
def load(name):return json.loads((ROOT/name).read_text())
class InternationalOpeningPriceTests(unittest.TestCase):
 def test_12_only_after_original_6057(self):
  old=load("preseason_2027_pre_international_20261027.json")
  new=load("preseason_2027_before_top100_20261027.json")
  final=load("preseason_2027.json")
  second=load("international_top100_noncollege_2027_priors.json")
  third=load("international_top100_staff_review_20271027.json")
  reviewed=load("international_pro_2027_market_priors.json")
  manifest=load("manifest_2027.json")
  r=reviewed["byESPNId"]
  exact={
   "5214635":3500000,"5281137":3500000,"5464194":3300000,
   "5458830":2500000,"5167829":2500000,"5110117":2300000,
   "5044386":1200000,"5351837":2000000,"5458832":2000000,
   "5458339":1500000,"5456498":700000,"5399797":1750000}
  self.assertEqual(r,exact)
  self.assertEqual(len(r),12)
  self.assertEqual(new["playerCount"],old["playerCount"])
  self.assertEqual(new["playerCount"],6057)
  self.assertEqual(set(old["byESPNId"]),set(new["byESPNId"]))
  differences={k for k in old["byESPNId"] if old["byESPNId"][k]!=new["byESPNId"][k]}
  self.assertEqual(differences,set(exact))
  self.assertEqual(new["byESPNId"],{**old["byESPNId"],**exact})
  self.assertEqual(reviewed["sourceBaselineByESPNId"],{id:old["byESPNId"][id] for id in exact})
  self.assertEqual(new["composition"]["internationalProfessionalReviewed"],12)
  self.assertEqual(manifest["baselinePlayerCount"],6057)
  self.assertFalse(manifest["dates"])
  self.assertFalse(manifest["months"])
  self.assertEqual(manifest["baselineVersion"],final["baselineVersion"])
  self.assertEqual(final["byESPNId"],{**new["byESPNId"],**second["byESPNId"],**third["byESPNId"]})
  self.assertEqual(sum(r.values())-sum(reviewed["sourceBaselineByESPNId"].values()),24952100)
 def test_no_staff_background_in_public_price_inputs(self):
  reviewed=load("international_pro_2027_market_priors.json")
  self.assertEqual(reviewed["sourceCategory"],"professional_experience_market_calibration")
  self.assertFalse(any(field in reviewed for field in ("kstateCommit","staffNotes","agent","askingPrice")))
if __name__=="__main__":unittest.main()
