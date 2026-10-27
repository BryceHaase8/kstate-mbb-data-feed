#!/usr/bin/env python3
"""2026-10-27 ESPN-ID roster additions: exact-preservation and coverage checks."""
import json,unittest
from pathlib import Path
P=Path(__file__).resolve().parents[1]
def read(path):return json.loads((P/path).read_text())
class PreseasonRosterGapQA(unittest.TestCase):
 def test_all_current_roster_ids_have_frozen_prices(self):
  rost=read("data/roster_2027_advanced.json")
  self.assertEqual(rost["rosterSeason"],2027)
  self.assertEqual(rost["totalTeams"],365)
  self.assertEqual(len(rost["players"]),5541)
  ids=[str(row[0]) for row in rost["players"]]
  self.assertEqual(len(ids),len(set(ids)))
  anchor=read("public/stock_watch/preseason_2027.json")
  base=read("public/stock_watch/preseason_2027_original_6010_2026_10_27.json")
  supplement=read("public/stock_watch/roster_2027_new_id_v4_proxy_addendum.json")
  prices=anchor["byESPNId"]
  self.assertEqual(anchor["asOf"],base["asOf"])
  self.assertEqual(anchor["playerCount"],6057)
  self.assertEqual(len(base["byESPNId"]),6010)
  self.assertEqual(len(supplement["byESPNId"]),47)
  self.assertFalse(set(base["byESPNId"]) & set(supplement["byESPNId"]))
  self.assertEqual(prices,{**base["byESPNId"],**supplement["byESPNId"]})
  self.assertEqual(set(ids)-set(prices),set(),"A verified October roster player has no NIL baseline")
 def test_source_labelling_and_uncertain_international(self):
  source=read("public/stock_watch/roster_2027_new_id_v4_proxy_addendum.json")
  methods=source["methodByESPNId"]
  self.assertEqual(sum(s=="V4_HISTORICAL_AUXILIARY_FROZEN" for s in methods.values()),9)
  self.assertEqual(sum(s=="V4_TEAM_COHORT_PROXY_NO_STATS" for s in methods.values()),38)
  self.assertEqual(source["players"]["5281137"]["name"],"Saliou Niang")
  self.assertEqual(source["players"]["5281137"]["confidence"],"LOW_PRESEASON_PROXY")
  self.assertTrue(all(isinstance(v,int) and 20000<=v<=20000000 for v in source["byESPNId"].values()))
  self.assertTrue(all(source["players"][k]["preseasonPrice"]==v for k,v in source["byESPNId"].items()))
if __name__=="__main__":unittest.main()
