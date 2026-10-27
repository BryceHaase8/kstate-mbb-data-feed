#!/usr/bin/env python3
"""No prior collegiate stats: exact-ID, top100, source and immutable price QA."""
import json,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1]
def load(path):return json.loads((R/path).read_text(encoding='utf-8'))
class Top100InternationalNoCollegeTests(unittest.TestCase):
 def test_selected_22_and_exclusions(self):
  q=load("research_qa/international_top100_no_college_review_2027.json")
  top=load("public/stock_watch/international_top100_noncollege_2027_priors.json")
  before=load("public/stock_watch/preseason_2027_before_top100_20261027.json")
  after=load("public/stock_watch/preseason_2027_before_staff_20261027.json")
  staff=load("public/stock_watch/international_pro_2027_market_priors.json")
  rows=q["rows"]
  assert len(rows)==138
  assert len(top["byESPNId"])==22
  assert len(staff["byESPNId"])==12
  assert len(q["excluded"])==2
  assert q["summary"]["remainingRequiresSourceReview"]==102
  assert all(r["torvikRank"]<=100 and r["noRecentESPN_D1History"] for r in rows)
  self.assertFalse(set(top["byESPNId"])&set(staff["byESPNId"]))
  self.assertFalse(set(top["byESPNId"])&set(q["excluded"]))
  self.assertTrue(all(row["reviewClass"]!="VERIFIED_NONCOLLEGE_RESEARCH_PRICE"
      or (row["espnId"] in top["byESPNId"] and row["evidenceUrl"].startswith("https://"))
      for row in rows))
  assert before["playerCount"]==after["playerCount"]==6057
  assert {k for k,v in before["byESPNId"].items() if after["byESPNId"][k]!=v}==set(top["byESPNId"])
  assert after["byESPNId"]=={**before["byESPNId"],**top["byESPNId"]}
  assert all(before["byESPNId"][k]==v for k,v in staff["byESPNId"].items())
  assert all(top["sourceBaselineByESPNId"][k]==before["byESPNId"][k] for k in top["byESPNId"])
  assert all(before["byESPNId"][k]<v for k,v in top["byESPNId"].items())
  assert sum(top["byESPNId"].values())-sum(top["sourceBaselineByESPNId"].values())==22938900
  self.assertEqual(after["byESPNId"]["5458320"],before["byESPNId"]["5458320"])
 def test_stock_watch_not_inflated(self):
  m=load("public/stock_watch/manifest_2027.json")
  assert not m["dates"] and not m["months"] and m["baselinePlayerCount"]==6057
  assert m["top100NoncollegeResearch"]["count"]==22
 def test_no_unverified_international_premium(self):
  q=load("research_qa/international_top100_no_college_review_2027.json")
  top=load("public/stock_watch/international_top100_noncollege_2027_priors.json")
  rowMap={r["espnId"]:r for r in q["rows"]}
  assert all(rowMap[k]["reviewClass"]=="VERIFIED_NONCOLLEGE_RESEARCH_PRICE" for k in top["byESPNId"])
  assert all(rowMap[k]["reviewClass"]=="UNVERIFIED_BACKGROUND_DO_NOT_AUTOPRICE"
             for k in set(rowMap)-set(top["byESPNId"])-set(q["excluded"])
             -{r["espnId"] for r in q["rows"] if r["reviewClass"]=="ALREADY_USER_ANCHORED"})
if __name__=="__main__":unittest.main()
