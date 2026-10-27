#!/usr/bin/env python3
"""No proprietary price labels; synthetic policy invariants only."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1] / "scripts" / "nil_model"))
from v4_relative_update_research import anchored_price, evidence_weight, compute

class RelativePriceTests(unittest.TestCase):
    def test_no_games_do_not_move_v4(self):
        self.assertEqual(anchored_price(900000, 600000, 1800000, 0, 0)[0], 900000)
    def test_model_disagreement_does_not_change_starting_price(self):
        self.assertEqual(anchored_price(900000, 600000, 600000, 30, 900)[0], 900000)
    def test_same_model_increase_is_mapped_to_v4(self):
        p, w = anchored_price(900000, 600000, 900000, 30, 900, 700, 30)
        self.assertGreater(w, .90)
        self.assertGreater(p, 1200000)
        self.assertLess(p, 1350000)
    def test_evidence_respects_minutes(self):
        self.assertGreater(evidence_weight(20, 600, 600, 25),
                           evidence_weight(20, 60, 600, 25))
    def test_anomalous_fourfold_jump_rejected(self):
        with self.assertRaises(ValueError):
            anchored_price(900000, 600000, 5000000, 6, 180)
    def test_no_relabelling_existing_model_as_v4(self):
        baseline = {"schemaVersion":1,"season":2027,"model":"NIL Estimation Model",
                    "provenance":"not a verified V4 file","asOf":"2026-10-24",
                    "byESPNId":{"5176309":900000}}
        ref = {"schemaVersion":1,"season":2027,"generatedAsOf":"2026-10-24",
               "baselineAsOf":"2026-10-24","modelVersion":"frozen-v1",
               "sourceFingerprint":"hash","byESPNId":{"5176309":600000}}
        now = {"schemaVersion":1,"season":2027,"generatedAsOf":"2026-11-05",
               "modelVersion":"frozen-v1","referenceFingerprint":"hash",
               "byESPNId":{"5176309":{"games":5,"minutes":120,"value":1000000}}}
        with self.assertRaises(ValueError):
            compute(baseline,ref,now,"2026-11-05")
        baseline["model"] = "V4_VERIFIED"
        out, audit = compute(baseline,ref,now,"2026-11-05")
        self.assertEqual(out["byESPNId"]["5176309"]["preseason"],900000)
        self.assertFalse(audit["publishReady"])
        now["modelVersion"] = "retrained-without-rebase"
        with self.assertRaises(ValueError):
            compute(baseline,ref,now,"2026-11-05")

if __name__=="__main__":
    unittest.main()
