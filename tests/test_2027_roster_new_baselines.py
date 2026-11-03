#!/usr/bin/env python3
"""Additive ESPN roster / original V4 opening-baseline QA, November 2026."""
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import urllib.error

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from refresh_2027_espn_rosters import roster as fetch_live_roster

def read(path):return json.loads((ROOT/path).read_text())
class NationalRosterPassQA(unittest.TestCase):
    def setUp(self):
        self.prev=read("public/stock_watch/preseason_2027.json")
        self.late=read("public/stock_watch/late_entrant_baselines_2027.json")
        self.roster=read("data/roster_2027_advanced.json")
        self.audit=read("data/roster_additions_2027_20261103.json")
    def test_immutable_original_6057(self):
        self.assertEqual(self.prev["playerCount"],6057)
        self.assertEqual(len(self.prev["byESPNId"]),6057)
        self.assertEqual(len(self.late["byESPNId"]),30)
        self.assertFalse(set(self.prev["byESPNId"]) & set(self.late["byESPNId"]))
    def test_added_athletes_are_exact_id_keyed_and_priced_once(self):
        ids=self.audit["additions"]
        self.assertEqual(len(ids),36)
        self.assertEqual(self.audit["newESPNIDs"],36)
        self.assertEqual(self.audit["teamsRequested"],365)
        self.assertGreaterEqual(self.audit["teamsVerified"],350)
        self.assertEqual(self.audit["pricingAudit"]["unpricedRemaining"],0)
        seen=set()
        for pid,entry in ids.items():
            self.assertTrue(pid.isdigit())
            self.assertNotIn(pid,seen)
            seen.add(pid)
            frozen=pid in self.prev["byESPNId"]
            late=pid in self.late["byESPNId"]
            self.assertNotEqual(frozen,late, "Exactly one frozen or late baseline for "+pid)
            if late:
                amount=self.late["byESPNId"][pid]["value"]
                self.assertEqual(type(amount),int)
                self.assertGreaterEqual(amount,20000)
                self.assertLessEqual(amount,20000000)
                self.assertEqual(self.late["byESPNId"][pid]["effectiveDate"][:7],
                                 "2026-10" if pid=="5468197" else "2026-11")
        self.assertEqual(self.audit["pricingAudit"]["addedOriginalV4"],24)
        self.assertEqual(self.audit["pricingAudit"]["addedV4CohortProxy"],4)
        self.assertEqual(self.audit["pricingAudit"]["addedHistoricalPriorPreserved"],1)
        self.assertEqual(self.audit["pricingAudit"]["alreadyFrozen"],6)
        self.assertEqual(self.audit["pricingAudit"]["alreadyLate"],1)
    def test_roster_school_and_identity_provenance(self):
        rows=self.roster["players"]
        byid={r[0]:r for r in rows}
        self.assertEqual(self.roster["schemaVersion"],3)
        self.assertEqual(self.roster["rosterSeason"],2027)
        self.assertEqual(self.roster["eligibilityTargetSeason"],"2027-28")
        self.assertEqual(len(rows),5575)
        self.assertEqual(len(byid),len(rows))
        self.assertEqual(len(self.roster["teams"]),365)
        for pid,entry in self.audit["additions"].items():
            self.assertIn(pid,byid)
            self.assertEqual(byid[pid][2],entry["teamId"])
            self.assertEqual(byid[pid][1],entry["name"])
        for pair in self.audit["supersededStagedRosterIds"]:
            self.assertIn(pair["current"],byid)
            self.assertNotIn(pair["old"],byid)
            self.assertIn(pair["old"],self.prev["byESPNId"])
            self.assertTrue(pair["oldHistoricalPricePreserved"])
    def test_espn_season_404_recovers_live_team_without_inventing_class(self):
        athletes=[{"id":str(5176140+i),"displayName":("Karon Boyd" if i==0 else "Player "+str(i)),
                   "active":True,"displayHeight":"6 ft 6 in", "displayWeight":"223 lbs",
                   "position":{"abbreviation":"F"}} for i in range(6)]
        def mock_open(request,timeout=22):
            if "/roster?" in request.full_url:
                raise urllib.error.HTTPError(request.full_url,404,"ESPN season roster missing",{},None)
            return io.BytesIO(json.dumps({"team":{"id":"2382","athletes":athletes}}).encode())
        with patch("refresh_2027_espn_rosters.urllib.request.urlopen",side_effect=mock_open):
            team,players,error=fetch_live_roster("2382")
        self.assertEqual(team,"2382")
        self.assertIsNone(error)
        self.assertEqual(len(players),6)
        self.assertEqual(players[0]["id"],"5176140")
        self.assertEqual(players[0]["schoolClass"],"")
        self.assertEqual(players[0]["source"],"ESPN_CURRENT_TEAM_ROSTER_FALLBACK_SEASON_404")

    def test_mercer_fallback_original_v4_and_class_are_audited(self):
        row=self.late["byESPNId"]["5176140"]
        self.assertEqual(row["value"],914723)
        self.assertEqual(row["sourcePreviouslyPublishedPreseason"],1053906)
        self.assertEqual(row["sourcePreviouslyPublishedAnchorType"],"V4_OR_ARCHIVED_ESPN")
        self.assertEqual(row["priorSchool"],"Wichita St.")
        self.assertEqual(row["priorGames"],35)
        self.assertIn("REVIEW_REQUIRED",row["eligibilityStatus"])
        self.assertEqual(self.audit["verifiedFallbackTeams"][0]["teamId"],"2382")
        self.assertEqual(self.audit["verifiedFallbackTeams"][0]["newlyDiscoveredESPNIDs"],["5176140"])

    def test_direct_v4_and_peer_proxies_never_misattributed(self):
        methods={}
        for pid,entry in self.audit["additions"].items():
            if pid not in self.late["byESPNId"] or pid=="5468197":continue
            row=self.late["byESPNId"][pid]
            method=row["modelVersion"]
            methods[method]=methods.get(method,0)+1
            self.assertIn(method,("Original V4 fair-market residual model","V4_TEAM_COHORT_PROXY","V4_ARCHIVED_ESPN_HISTORICAL_PRIOR_PRESERVED"))
            if method=="V4_TEAM_COHORT_PROXY":
                self.assertEqual(row["confidence"],"LOW_CONFIDENCE_NO_DIRECT_V4")
                self.assertIn("peerContext",row)
                self.assertGreater(row["peerContext"]["originalV4PeersAtTeam"],2)
            elif method=="Original V4 fair-market residual model":
                self.assertIn("TORVIK_2025_26",row["source"])
                self.assertNotIn("peerContext",row)
            else:
                self.assertEqual(pid,"5105974")
                self.assertEqual(row["value"],676851)
                self.assertEqual(row["sourcePreviouslyPublishedPreseason"],676851)
                self.assertNotIn("peerContext",row)
        self.assertEqual(methods,{"Original V4 fair-market residual model":24,
                                 "V4_TEAM_COHORT_PROXY":4,
                                 "V4_ARCHIVED_ESPN_HISTORICAL_PRIOR_PRESERVED":1})
        # Prevent mistaking another 6-5 Noah Williams for the new 6-8 Bradley
        # athlete and accidentally assigning his unrelated prior-year V4.
        self.assertEqual(self.late["byESPNId"]["4873205"]["espnIdSupersedesStagedId"],"5460113")
        self.assertEqual(self.late["byESPNId"]["5317687"]["espnIdSupersedesStagedId"],"5461303")
        for id in ("4873205","5317687"):
            self.assertEqual(self.late["byESPNId"][id]["modelVersion"],"V4_TEAM_COHORT_PROXY")

if __name__=="__main__":unittest.main()
