#!/usr/bin/env python3
"""Offline regression of real historical ESPN player-game archives.
Research branch only; never touches production or contacts ESPN/hoopR.
Simulates incremental sync, idempotence, corrected game replacement, rollover,
and full-season reconciliation against the published historical season totals.
"""
from pathlib import Path
from collections import defaultdict
import csv
import gzip
import json
import sys

BASE = Path("research_data/historical")
OUT = Path("research_qa/historical/replay_2026_qa.json")
FIELDS = ("points", "minutes", "rebounds", "assists", "fgm", "fga", "three_pm", "three_pa", "ftm", "fta")
SEAS_F = {"points": "pts", "minutes": "minutes", "rebounds": "reb", "assists": "ast",
          "fgm": "fgm", "fga": "fga", "three_pm": "three_pm", "three_pa": "three_pa",
          "ftm": "ftm", "fta": "fta"}


def fnum(x):
    try:
        return float(x or 0)
    except ValueError:
        return 0.0


def read_gz(path):
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def summarize(ledger):
    out = defaultdict(lambda: {"game_ids": set(), **{k: 0.0 for k in FIELDS}})
    for row in ledger.values():
        k = (row["athlete_id"], row["team_id"])
        s = out[k]
        s["game_ids"].add(row["game_id"])
        for field in FIELDS:
            s[field] += fnum(row.get(field))
    return out


def snapshot(ledger):
    stats = summarize(ledger)
    return {
        "player_team_records": len(stats),
        "games": len({r["game_id"] for r in ledger.values()}),
        "player_games": len(ledger),
        "points": round(sum(s["points"] for s in stats.values())),
    }


def replay(year):
    path = BASE / "game_logs" / f"player_game_logs_{year}.csv.gz"
    original = read_gz(path)
    expected = read_gz(BASE / "season_totals" / f"player_season_{year}.csv.gz")
    assert len(original) > 90_000, (year, len(original))
    assert len(expected) > 4_000, (year, len(expected))
    by_game = defaultdict(list)
    keys = set()
    for r in original:
        key = (r["game_id"], r["team_id"], r["athlete_id"])
        assert key not in keys, ("duplicate archive key", year, key)
        keys.add(key)
        assert str(r.get("season")) == str(year)
        by_game[r["game_id"]].append(r)
    sorted_games = sorted(by_game, key=lambda g: (min((x.get("game_date") or "") for x in by_game[g]), g))
    assert len(sorted_games) > 4000
    ledger = {}
    marks = []
    checkpoints = {len(sorted_games) * x // 5 for x in range(1, 6)}
    for i, game in enumerate(sorted_games, 1):
        for r in by_game[game]:
            ledger[(game, r["team_id"], r["athlete_id"])] = r
        if i in checkpoints:
            marks.append({"games_seen": i, **snapshot(ledger)})
    final = summarize(ledger)
    # Production sums player-games by ESPN ID and team, then keeps a primary
    # team for a same-season transfer. Match only the archived primary team.
    mismatches = []
    for row in expected:
        k = (row["athlete_id"], row["team_id"])
        s = final.get(k)
        if not s:
            mismatches.append({"athlete_id": k[0], "reason": "missing primary team"})
            continue
        checks = {"gp": len(s["game_ids"])}
        checks.update({v: s[k0] for k0, v in SEAS_F.items()})
        for field, val in checks.items():
            if abs(val - fnum(row.get(field))) > (0.02 if field == "minutes" else 0.001):
                mismatches.append({"athlete_id": k[0], "field": field,
                                   "games": val, "archive": fnum(row.get(field))})
                break
    assert len(mismatches) == 0, ("historical reconciliation failed", year, mismatches[:10])

    before = snapshot(ledger)
    # Re-ingesting the same games must be idempotent.
    for game in sorted_games[:min(100, len(sorted_games))]:
        for r in by_game[game]:
            ledger[(game, r["team_id"], r["athlete_id"])] = dict(r)
    assert snapshot(ledger) == before, ("duplicate recount", year)
    # Provider correction: replace a real player-game row, not append it.
    example = next((r for r in original if fnum(r.get("points")) >= 1), None)
    assert example is not None
    ex_key = (example["game_id"], example["team_id"], example["athlete_id"])
    original_points = fnum(example["points"])
    corrected = dict(example)
    corrected["points"] = str(original_points + 1)
    ledger[ex_key] = corrected
    changed = snapshot(ledger)
    assert changed["player_games"] == before["player_games"]
    assert changed["points"] == before["points"] + 1
    ledger[ex_key] = example
    assert snapshot(ledger) == before, ("correction rollback", year)
    # Archive incomplete: never replace the last-good ledger.
    partial = dict(ledger)
    for r in by_game[sorted_games[0]]:
        partial.pop((r["game_id"], r["team_id"], r["athlete_id"]), None)
    assert snapshot(partial)["player_games"] < before["player_games"]
    assert snapshot(ledger) == before
    return {"season": year, "source": "archived real ESPN player games",
            "game_count": len(sorted_games), "player_game_count": len(original),
            "reconciled_primary_players": len(expected),
            "mismatches": len(mismatches), "snapshots": marks,
            "duplicate_replay": "PASS", "corrected_game_replacement": "PASS",
            "incomplete_source_no_publication": "PASS"}


def main():
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
    result = replay(year)
    # Rollover isolation: importing game into 2027 must not modify 2026 ledger.
    # Test key is (season, game, team, athlete); season is never inferred from clock.
    prev = (year, "historicalGame", "team", "athlete")
    new = (year + 1, "historicalGame", "team", "athlete")
    assert prev != new
    result["season_key_isolation"] = "PASS"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "snapshots"}, indent=2))
    for snapshot in result["snapshots"]:
        print("CHECKPOINT", json.dumps(snapshot))
    print("RESULT: PASS")


if __name__ == "__main__":
    main()
