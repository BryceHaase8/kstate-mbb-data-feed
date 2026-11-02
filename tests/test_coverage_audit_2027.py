#!/usr/bin/env python3
"""Coverage, backlog, and scheduled-monitor QA; never calls ESPN or GitHub."""
import datetime as dt
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import audit_2027_coverage as audit


def event(gid, home=80, away=70, completed=True):
    return {"id": str(gid), "season": {"year": 2027, "type": 2},
            "status": {"type": {"completed": completed}},
            "competitions": [{"competitors": [
                {"score": str(home)}, {"score": str(away)}]}]}


def box(score=(70, 80)):
    return {"scores": {score}, "athletes": {"123": {"pts": 11, "reb": 4, "ast": 2}}}


def fetcher(days, raise_on=()):
    def fetch(url):
        day = url.split("dates=")[1][:8]
        if day in raise_on:
            raise OSError("ESPN scoreboard temporarily unavailable")
        return {"events": days.get(day, [])}
    return fetch


class CoverageAuditTests(unittest.TestCase):
    def test_all_182_games_covered(self):
        ids = [str(401900000 + n) for n in range(182)]
        events = [event(gid) for gid in ids]
        prior = {}
        games = {gid: box() for gid in ids}
        result = audit.build_report(
            dt.date(2026, 11, 2), games, prior=prior,
            fetch=fetcher({"20261102": events}), window_days=2)
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(result["totalCompletedGamesObserved"], 182)
        self.assertEqual(result["verifiedCompletedGames"], 182)
        self.assertEqual(result["missingGameIds"], [])
        self.assertEqual(result["unresolvedByDate"], {})

    def test_missing_games_are_reported_and_carried_over(self):
        ids = [str(401900000 + n) for n in range(182)]
        events = [event(gid) for gid in ids]
        published = {gid: box() for gid in ids[:-3]}
        first = audit.build_report(
            dt.date(2026, 11, 2), published,
            fetch=fetcher({"20261102": events}), window_days=2)
        self.assertEqual(first["status"], "INCOMPLETE")
        self.assertEqual(first["verifiedCompletedGames"], 179)
        self.assertEqual(first["missingGameIds"], ids[-3:])
        self.assertEqual(first["unresolvedByDate"]["2026-11-02"], ids[-3:])
        # Thirty days later, those games are still outstanding, not silently
        # dropped when the 21-day rolling scoreboard scan expires.
        later = audit.build_report(
            dt.date(2026, 12, 5), published, prior=first,
            fetch=fetcher({"20261102": events}), window_days=2)
        self.assertEqual(later["missingGameIds"], ids[-3:])
        self.assertIn("2026-11-02", later["unresolvedByDate"])
        repaired = audit.build_report(
            dt.date(2026, 12, 6), {gid: box() for gid in ids}, prior=later,
            fetch=fetcher({"20261102": events}), window_days=2)
        self.assertEqual(repaired["status"], "COMPLETE")
        self.assertEqual(repaired["missingGameIds"], [])
        self.assertEqual(repaired["totalCompletedGamesObserved"], 182)

    def test_score_change_cannot_appear_healthy(self):
        result = audit.build_report(
            dt.date(2026, 11, 1), {"401999001": box()},
            fetch=fetcher({"20261101": [event("401999001", 81, 70)]}),
            window_days=1)
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertEqual(result["scoreMismatchGameIds"], ["401999001"])
        self.assertEqual(result["verifiedCompletedGames"], 0)

    def test_espn_outage_retains_observed_games_and_marks_degraded(self):
        first = audit.build_report(
            dt.date(2026, 11, 1), {"401999001": box()},
            fetch=fetcher({"20261101": [event("401999001")]}), window_days=1)
        retry = audit.build_report(
            dt.date(2026, 11, 2), {"401999001": box()}, prior=first,
            fetch=fetcher({}, raise_on=["20261101"]), window_days=2)
        self.assertEqual(retry["status"], "SOURCE_DEGRADED")
        self.assertEqual(retry["verifiedCompletedGames"], 1)
        self.assertEqual(retry["sourceErrors"][0]["date"], "2026-11-01")
        self.assertIn("401999001", retry["completedByDate"]["2026-11-01"])

    def test_espn_empty_day_does_not_erase_previous_final(self):
        first = audit.build_report(
            dt.date(2026, 11, 1), {"401999001": box()},
            fetch=fetcher({"20261101": [event("401999001")]}), window_days=1)
        next_report = audit.build_report(
            dt.date(2026, 11, 2), {"401999001": box()}, prior=first,
            fetch=fetcher({}), window_days=2)
        self.assertEqual(next_report["status"], "SOURCE_DEGRADED")
        self.assertEqual(next_report["sourceDisappearedDates"], ["2026-11-01"])
        self.assertEqual(next_report["totalCompletedGamesObserved"], 1)

    def test_overlapping_overnight_game_dates_are_flagged_without_blocking(self):
        published = {"401999001": box()}
        result = audit.build_report(
            dt.date(2026, 11, 2), published,
            fetch=fetcher({
                "20261101": [event("401999001")],
                "20261102": [event("401999001")]
            }), window_days=2)
        self.assertEqual(result["verifiedCompletedGames"], 1)
        self.assertEqual(result["totalCompletedGamesObserved"], 1)
        self.assertEqual(result["duplicateSourceGameIds"], ["401999001"])
        self.assertEqual(result["status"], "SOURCE_DEGRADED")

    def test_scheduler_heartbeat_stale(self):
        now = dt.datetime(2026, 11, 2, 22, 0, tzinfo=dt.timezone.utc)
        old = {
            "head_branch": "main", "event": "schedule",
            "created_at": "2026-11-02T17:00:00Z"}
        def fake(url, token=None):
            return {"workflow_runs": [old]}
        result = audit.audit_monitor("owner/repo", "test", now, fetch=fake)
        self.assertEqual(result["status"], "STALE")
        self.assertGreater(result["ageMinutes"], 90)

    def test_scheduler_heartbeat_healthy(self):
        now = dt.datetime(2026, 11, 2, 22, 0, tzinfo=dt.timezone.utc)
        recent = {
            "head_branch": "main", "event": "schedule",
            "created_at": "2026-11-02T21:38:00Z"}
        def fake(url, token=None):
            return {"workflow_runs": [recent]}
        result = audit.audit_monitor("owner/repo", "test", now, fetch=fake)
        self.assertEqual(result["status"], "HEALTHY")


if __name__ == "__main__":
    unittest.main()
