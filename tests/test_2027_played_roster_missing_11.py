#!/usr/bin/env python3
"""Exact-ID 11-player late-NIL research audit; cannot silently rewrite original prices."""
import json, pathlib, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
IDS=set(["4075245","5184894","5237343","5240515","5280898","5351298","5351500","5455867","5459577","5460603","5461587"])
PRICES={"4075245":40000,"5184894":32000,"5237343":175000,"5240515":31000,"5280898":347000,"5351298":190000,"5351500":77000,"5455867":25000,"5459577":49000,"5460603":77000,"5461587":71000}
def load(path):return json.loads((ROOT/path).read_text())
class VerifiedGameLogAdditions(unittest.TestCase):
 def test_approved_ids_and_dollar_prices(self):
  doc=load("public/stock_watch/late_entrant_baselines_2027.json")
  original=load("public/stock_watch/preseason_2027.json")["byESPNId"]
  prices=doc["byESPNId"]
  self.assertFalse(IDS & set(original))
  for id in IDS:
   self.assertEqual(prices[id]["value"],PRICES[id])
   self.assertEqual(prices[id]["effectiveDate"],"2026-11-06")
   self.assertIn("2026-11-06",prices[id]["approvedBy"])
  self.assertEqual(len(prices),46)
  self.assertEqual(len(original),6057)
 def test_players_have_matching_2027_espn_id_and_school(self):
  roster=load("data/roster_2027_advanced.json")
  rows={str(row[0]):row for row in roster["players"]}
  prices=load("public/stock_watch/late_entrant_baselines_2027.json")["byESPNId"]
  self.assertEqual(len(rows),5587)
  for id in IDS:
   row=rows[id]
   self.assertEqual(row[1],prices[id]["playerName"])
   self.assertEqual(row[2],prices[id]["teamId"])
   self.assertEqual(roster["teams"][row[2]],prices[id]["teamName"])
   self.assertTrue(row[8] in (0,2))
 def test_early_game_logs_exist_before_any_estimate(self):
  logs=ROOT/"public/portal_game_logs_2027"
  for id in IDS:
   file=logs/("games_%03d.json"%(int(id)%128))
   self.assertTrue(file.is_file(),str(file))
   shard=json.loads(file.read_text())
   self.assertIn(id,shard["players"])
   self.assertGreater(len(shard["players"][id]),0)
if __name__=="__main__":unittest.main()
