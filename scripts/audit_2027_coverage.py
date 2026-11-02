#!/usr/bin/env python3
"""2026–27 ESPN final-game coverage audit.

Official finalized scoreboard games are compared with the player-game shard
manifest, never used to fabricate player statistics. This audit is intentionally
non-blocking on missing ESPN boxes: existing valid facts must still publish.
Missing IDs and their dates persist until verified, even beyond the normal
21-day collection lookback. Source failures never become false COMPLETE.
"""
import datetime as dt
import json
import os
from pathlib import Path
import sys

from check_espn_game_updates import (
    CHICAGO, API, final_games, get_json, load_published,
)

START = dt.date(2026, 11, 1)
END = dt.date(2027, 4, 30)
WINDOW_DAYS = 21
REPORT_PATH = Path("public/portal_game_logs_2027/coverage.json")
ACTIVE_MONITOR_HOURS = set(range(11, 24)) | set(range(0, 4))


def audit_monitor(repository, token, now, fetch=get_json):
    """Read-only scheduler heartbeat; a missing monitor is never hidden."""
    local = now.astimezone(CHICAGO)
    result = {"status": "OUTSIDE_GAME_WINDOW", "lastScheduledAt": None}
    if local.month not in (11, 12, 1, 2, 3, 4) or local.hour not in ACTIVE_MONITOR_HOURS:
        return result
    if not repository or not token:
        return {"status": "UNKNOWN", "reason": "GitHub Actions token unavailable",
                "lastScheduledAt": None}
    url = API + "/repos/" + repository + "/actions/workflows/espn-game-monitor.yml/runs?per_page=40"
    try:
        runs = (fetch(url, token=token) or {}).get("workflow_runs") or []
        dates = [
            dt.datetime.fromisoformat(str(run["created_at"]).replace("Z", "+00:00"))
            for run in runs
            if run.get("event") == "schedule" and run.get("head_branch") == "main"
            and run.get("created_at")
        ]
        if not dates:
            return {"status": "STALE", "reason": "No scheduled monitor execution found",
                    "lastScheduledAt": None}
        latest = max(dates)
        age = (now - latest).total_seconds() / 60
        return {"status": "HEALTHY" if age <= 90 else "STALE",
                "lastScheduledAt": latest.isoformat().replace("+00:00", "Z"),
                "ageMinutes": round(age, 1)}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {"status": "UNKNOWN", "reason": str(exc)[:250],
                "lastScheduledAt": None}


def build_report(today, published, prior=None, fetch=get_json, window_days=WINDOW_DAYS,
                 now=None, monitor_health=None):
    """Purely reconcile final-score evidence; preserve all previously seen IDs."""
    if not START <= today <= END:
        raise ValueError("Audit outside NCAA 2026–27 active season")
    if not 1 <= window_days <= 220:
        raise ValueError("Invalid coverage audit window")
    prior = prior or {}
    before = prior.get("completedByDate") or {}
    if not isinstance(before, dict):
        raise ValueError("Malformed prior coverage ledger")
    ledger = {
        str(day): {
            str(gid): list(pair)
            for gid, pair in games.items()
            if str(gid).isdigit() and isinstance(pair, (list, tuple)) and len(pair) == 2
        }
        for day, games in before.items() if isinstance(games, dict)
    }
    first = max(START, today - dt.timedelta(days=window_days-1))
    scan_dates = {first + dt.timedelta(days=x) for x in range((today-first).days+1)}
    # Also recheck older unresolved dates, including score corrections.
    for value in (prior.get("unresolvedByDate") or {}):
        try:
            day = dt.date.fromisoformat(value)
        except ValueError:
            continue
        if START <= day <= today:
            scan_dates.add(day)
    errors, shrunk = [], []
    for day in sorted(scan_dates):
        key = day.isoformat()
        old = ledger.get(key, {})
        try:
            finals = final_games(day, fetch=fetch, lookback_days=1)
            new = {gid: list(scores) for gid, scores in finals.items()}
            # ESPN can transiently omit games after publication. Do not erase
            # previously observed completed events on an intermittent response.
            if set(old) - set(new):
                shrunk.append(key)
            ledger[key] = {**old, **new}
        except (OSError, ValueError, TypeError, KeyError) as exc:
            errors.append({"date": key, "reason": str(exc)[:250]})
    ledger = {day: vals for day, vals in sorted(ledger.items()) if vals}
    missing, corrected, unresolved = [], [], {}
    expected = set()
    verified = 0
    for day, games in ledger.items():
        for gid, score in games.items():
            expected.add(gid)
            entry = published.get(gid)
            if not entry:
                missing.append(gid)
                unresolved.setdefault(day, []).append(gid)
            elif tuple(score) not in entry["scores"]:
                corrected.append(gid)
                unresolved.setdefault(day, []).append(gid)
            else:
                verified += 1
    if len(expected) != sum(len(g) for g in ledger.values()):
        raise ValueError("ESPN game ID associated with multiple scoreboard dates")
    status = ("INCOMPLETE" if missing or corrected else
              "SOURCE_DEGRADED" if errors or shrunk else "COMPLETE")
    checked_at = now or dt.datetime.now(dt.timezone.utc)
    return {
        "schemaVersion": 1,
        "season": 2027,
        "checkedAt": checked_at.isoformat().replace("+00:00", "Z"),
        "status": status,
        "firstSeasonDate": START.isoformat(),
        "latestScannedDate": today.isoformat(),
        "routineLookbackDays": window_days,
        "sourceDaysChecked": len(scan_dates),
        "totalCompletedGamesObserved": len(expected),
        "verifiedCompletedGames": verified,
        "publishedTotalGames": len(published),
        "missingGameIds": sorted(missing),
        "scoreMismatchGameIds": sorted(corrected),
        "unresolvedByDate": {day: sorted(ids) for day, ids in sorted(unresolved.items())},
        "completedByDate": ledger,
        "sourceErrors": errors,
        "sourceDisappearedDates": sorted(set(shrunk)),
        "monitorHealth": monitor_health or {"status": "NOT_CHECKED"},
        "dataIntegrity": "ALREADY_VALIDATED_BY_FACTUAL_QA",
        "note": "Verified data remains publishable when missing ESPN game boxes are pending."
    }


def emit_report(report):
    print("ESPN 2027 COVERAGE:", json.dumps({
        "status": report["status"], "finals": report["totalCompletedGamesObserved"],
        "verified": report["verifiedCompletedGames"],
        "missing": len(report["missingGameIds"]),
        "scoreMismatch": len(report["scoreMismatchGameIds"]),
        "sourceErrors": len(report["sourceErrors"]),
        "monitor": report["monitorHealth"]["status"]
    }), flush=True)
    if report["missingGameIds"] or report["scoreMismatchGameIds"]:
        print("::warning::ESPN game coverage incomplete: %d missing; %d corrected scores needed. "
              "Future refreshes will retry unresolved games." %
              (len(report["missingGameIds"]), len(report["scoreMismatchGameIds"])), flush=True)
    if report["sourceErrors"] or report["sourceDisappearedDates"]:
        print("::warning::ESPN scoreboard partially unavailable or inconsistent; "
              "previously observed finals retained.", flush=True)
    if report["monitorHealth"]["status"] == "STALE":
        print("::warning::15-minute ESPN monitor execution is stale; "
              "scheduled full-refresh backup remains enabled.", flush=True)
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as out:
            out.write("\n### Verified ESPN Game Coverage — 2026–27\n\n")
            out.write("| Status | ESPN finals observed | Verified | Missing | Score corrections | Monitor |\n")
            out.write("|---|---:|---:|---:|---:|---|\n")
            out.write("| %s | %d | %d | %d | %d | %s |\n\n" % (
                report["status"], report["totalCompletedGamesObserved"],
                report["verifiedCompletedGames"], len(report["missingGameIds"]),
                len(report["scoreMismatchGameIds"]), report["monitorHealth"]["status"]))
            pending = report["missingGameIds"] + report["scoreMismatchGameIds"]
            if pending:
                out.write("**Pending game IDs:** " + ", ".join(pending[:100]) + "\n\n")
            if report["sourceErrors"]:
                out.write("**Scoreboard errors:** " +
                          ", ".join(e["date"] for e in report["sourceErrors"]) + "\n\n")


def main():
    today = dt.datetime.now(CHICAGO).date()
    if not START <= today <= END:
        print("ESPN coverage audit outside active season; no publication changes")
        return 0
    # Fail closed on malformed game shards, but never suppress otherwise valid
    # player box data solely because ESPN has not supplied another box yet.
    published = load_published()
    prior = json.loads(REPORT_PATH.read_text()) if REPORT_PATH.exists() else {}
    now = dt.datetime.now(dt.timezone.utc)
    monitor = audit_monitor(os.getenv("GITHUB_REPOSITORY"), os.getenv("GH_TOKEN"), now)
    report = build_report(today, published, prior=prior, now=now,
                          monitor_health=monitor)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp = REPORT_PATH.with_suffix(".tmp")
    temp.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    temp.replace(REPORT_PATH)
    emit_report(report)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as error:
        print("COVERAGE AUDIT BLOCKED UNVERIFIED MANIFEST: " + str(error), file=sys.stderr)
        sys.exit(1)
