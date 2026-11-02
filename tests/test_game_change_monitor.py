#!/usr/bin/env python3
"""Pure, offline regression checks for ESPN checker; no ESPN/GitHub calls."""
import datetime as dt
import json
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "game_monitor", Path(__file__).resolve().parents[1] / "scripts/check_espn_game_updates.py")
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def scoreboard(url):
    date = url.split("dates=")[1][:8]
    events = []
    if date == "20261104":
        events = [
            {"id": "401999001", "status": {"type": {"completed": True}},
             "competitions": [{"competitors": [{"score": "80"}, {"score": "77"}]}]},
            {"id": "401999002", "status": {"type": {"completed": False}},
             "competitions": [{"competitors": [{"score": "30"}, {"score": "28"}]}]}
        ]
    return {"events": events}


class GameMonitorTests(unittest.TestCase):
    def test_finals_only_includes_completed(self):
        games = mod.final_games(dt.date(2026, 11, 4), fetch=scoreboard)
        self.assertEqual(games, {"401999001": (77, 80)})

    def test_seven_day_recovery_window(self):
        urls = []
        def fake(url):
            urls.append(url)
            return {"events": []}
        mod.final_games(dt.date(2026, 11, 11), fetch=fake)
        self.assertEqual(len(urls), 7)
        self.assertIn("20261105", urls[0])
        self.assertIn("20261111", urls[-1])

    def test_corrected_box_dispatch_sends_forced_ids(self):
        posted = []
        class Response:
            status = 204
            def __enter__(self): return self
            def __exit__(self, *args): return False
        def send(request, timeout=15):
            posted.append(json.loads(request.data.decode()))
            return Response()
        with patch.object(mod.urllib.request, "urlopen", send):
            mod.dispatch_refresh("example/repo", "test-token",
                ["401999001", "401999002", "401999001", "bad"])
        self.assertEqual(posted[0]["inputs"]["season"], "2027")
        self.assertEqual(posted[0]["inputs"]["refresh_games"], "401999001,401999002")

    def test_early_november_ignores_prior_season_dates(self):
        urls = []
        def fetch(url):
            urls.append(url)
            return {"events": []}
        mod.final_games(dt.date(2026, 11, 1), fetch=fetch)
        self.assertEqual(len(urls), 1)
        self.assertIn("20261101", urls[0])

    def test_other_season_final_does_not_trigger(self):
        def fetch(url):
            return {"events": [{"id": "401999003",
              "season": {"year": 2026, "type": 2},
              "status": {"type": {"completed": True}},
              "competitions": [{"competitors": [{"score": 80}, {"score": 79}]}]}]}
        self.assertEqual(mod.final_games(dt.date(2026, 11, 1), fetch=fetch), {})

    def test_new_final_game_triggers(self):
        missing, changed = mod.compare_finals({"401999001": (77, 80)}, {}, slot=0)
        self.assertEqual(missing, ["401999001"])
        self.assertEqual(changed, [])

    def test_existing_game_unchanged(self):
        published = {"401999001": {"scores": {(77, 80)}, "athletes": {
            "123": {"pts": 21, "reb": 6, "ast": 3, "fgm": 7, "fga": 9}
        }}}
        def fetch(url):
            return {"boxscore": {"players": [{
                "statistics": [{"labels": ["PTS", "REB", "AST", "FG"],
                                "athletes": [{"athlete": {"id": "123"},
                                              "stats": ["21", "6", "3", "7-9"]}]}]
            }]}}
        self.assertEqual(mod.compare_finals({"401999001": (77, 80)}, published, fetch, slot=0), ([], []))

    def test_corrected_player_box_triggers(self):
        published = {"401999001": {"scores": {(77, 80)}, "athletes": {
            "123": {"pts": 21, "reb": 6, "ast": 3}
        }}}
        def fetch(url):
            return {"boxscore": {"players": [{
                "statistics": [{"labels": ["PTS", "REB", "AST"],
                                "athletes": [{"athlete": {"id": "123"},
                                              "stats": ["23", "6", "3"]}]}]
            }]}}
        self.assertEqual(mod.compare_finals({"401999001": (77, 80)}, published, fetch, slot=0),
                         ([], ["401999001:box_correction"]))

    def test_final_score_change_triggers_without_summary(self):
        published = {"401999001": {"scores": {(77, 80)}, "athletes": {}}}
        missing, changed = mod.compare_finals({"401999001": (78, 80)}, published, slot=0)
        self.assertEqual(missing, [])
        self.assertEqual(changed, ["401999001:final_score"])

    def test_unavailable_summary_never_invents_correction(self):
        published = {"401999001": {"scores": {(77, 80)}, "athletes": {
            "123": {"pts": 21, "reb": 6, "ast": 3}
        }}}
        def fail(url):
            raise OSError("summary unavailable")
        self.assertEqual(mod.compare_finals({"401999001": (77, 80)}, published, fail, slot=0), ([], []))

    def test_running_full_refresh_blocks_dispatch(self):
        def fetch(url, token=None):
            return {"workflow_runs": [{"head_branch": "main", "status": "in_progress",
                  "event": "schedule"}]}
        self.assertFalse(mod.dispatch_allowed("example/repo", "token", fetch)[0])

    def test_cooldown_blocks_repeat_dispatch(self):
        now = dt.datetime(2026, 11, 5, 2, 0, tzinfo=dt.timezone.utc)
        def fetch(url, token=None):
            return {"workflow_runs": [{"head_branch": "main", "status": "completed",
               "event": "workflow_dispatch", "created_at": "2026-11-05T01:40:00Z"}]}
        allowed, why = mod.dispatch_allowed("example/repo", "token", fetch, now=now)
        self.assertFalse(allowed)
        self.assertIn("cooldown", why.lower())

    def test_no_active_full_allows_dispatch(self):
        self.assertTrue(mod.dispatch_allowed("example/repo", "token",
              lambda url, token=None: {"workflow_runs": []})[0])

    def test_missing_partial_shards_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "manifest.json").write_text(
                '{"season":2027,"shards":128,"gamesVerified":1}')
            with self.assertRaisesRegex(ValueError, "shard missing"):
                mod.load_published(root)

    def test_no_manifest_is_valid_preseason(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(mod.load_published(Path(folder)), {})

    def test_summary_requires_verified_scoring_fields(self):
        self.assertEqual(mod.summary_stats("401999001", fetch=lambda url: {
            "boxscore": {"players": [{"statistics": [{"labels": ["PTS", "REB", "AST"],
             "athletes": [{"athlete": {"id": "123"}, "stats": ["17", "3", "2"]}]}]}]}}),
                         {"123": {"pts": 17, "reb": 3, "ast": 2}})


if __name__ == "__main__":
    unittest.main()
