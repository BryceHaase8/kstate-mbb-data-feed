#!/usr/bin/env python3
"""Fast ESPN final-game monitor. Only the validated daily workflow publishes data.

No data mutations here: compare ESPN final results / a rotating sample of
individual box scores to the already-published 2027 game-log shards, then
request an existing full refresh if needed. Never write a false baseline.
"""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

ESPN = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball"
API = "https://api.github.com"
CHICAGO = ZoneInfo("America/Chicago")
GAME_LOG_DIR = Path("public/portal_game_logs_2027")
COOLDOWN_MINUTES = 45
SUMMARY_LIMIT = 6
FIELDS = ("pts", "reb", "ast", "fgm", "fga", "threePm", "threePa", "ftm", "fta")


def get_json(url, token=None, timeout=15):
    headers = {"Accept": "application/vnd.github+json" if token else "application/json",
               "User-Agent": "kstate-portal-verified-game-monitor/1.0"}
    if token:
        headers["Authorization"] = "Bearer " + token
        headers["X-GitHub-Api-Version"] = "2022-11-28"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def load_published(path=GAME_LOG_DIR):
    """An empty map is valid before first-game shards exist.

    Never trust partially published shards. A valid manifest and all 128 shards
    are needed; otherwise fail closed rather than dispatching in a loop.
    """
    manifest_path = path / "manifest.json"
    if not manifest_path.exists():
        return {}
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("season") != 2027 or manifest.get("shards") != 128:
        raise ValueError("Game-log manifest is malformed")
    output = {}
    for shard in range(128):
        file = path / ("games_%03d.json" % shard)
        if not file.exists():
            raise ValueError("Published game-log shard missing: " + file.name)
        doc = json.loads(file.read_text())
        if doc.get("season") != 2027 or doc.get("shard") != shard:
            raise ValueError("Game-log shard identity mismatch: " + file.name)
        fields = doc.get("fields") or []
        if not all(f in fields for f in ("gameId", "teamScore", "opponentScore", *FIELDS)):
            raise ValueError("Game-log schema missing expected scoring fields")
        index = {name: fields.index(name) for name in fields}
        for athlete_id, rows in (doc.get("players") or {}).items():
            for row in rows:
                game_id = str(row[index["gameId"]])
                if not game_id.isdigit():
                    continue
                item = output.setdefault(game_id, {"scores": set(), "athletes": {}})
                pair = (int(row[index["teamScore"]]), int(row[index["opponentScore"]]))
                item["scores"].add(tuple(sorted(pair)))
                item["athletes"][str(athlete_id)] = {
                    field: int(row[index[field]]) for field in FIELDS
                }
    if manifest.get("gamesVerified") != len(output):
        raise ValueError("Game-log shard coverage differs from manifest")
    return output


def final_games(today, fetch=get_json):
    """Return official D-I final events over a rolling 3-calendar-day window."""
    games = {}
    for days_back in (2, 1, 0):
        candidate_date = today - dt.timedelta(days=days_back)
        if candidate_date < dt.date(2026, 11, 1):
            continue
        day = candidate_date.strftime("%Y%m%d")
        url = ESPN + "/scoreboard?" + urllib.parse.urlencode({
            "dates": day, "groups": "50", "limit": "500"
        })
        payload = fetch(url)
        if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
            raise ValueError("ESPN scoreboard unavailable for " + day)
        for event in payload["events"]:
            game_id = str(event.get("id") or "")
            season = event.get("season") or {}
            if season.get("year") not in (None, 2027):
                continue
            if season.get("type") not in (None, 2, 3):
                continue
            if not game_id.isdigit():
                continue
            status = event.get("status") or {}
            competitions = event.get("competitions") or []
            completed = (status.get("type") or {}).get("completed") is True
            if not completed or not competitions:
                continue
            teams = competitions[0].get("competitors") or []
            if len(teams) < 2:
                continue
            try:
                scores = tuple(sorted(int(float(t["score"])) for t in teams))
            except (KeyError, TypeError, ValueError):
                continue  # Not a validated final score.
            games[game_id] = scores
    return games


def stat_line(label, value):
    if value in (None, "", "--", "-"):
        return None
    if label in ("FG", "3PT", "FT"):
        parts = str(value).split("-")
        if len(parts) != 2:
            return None
        try:
            return tuple(int(p.strip()) for p in parts)
        except ValueError:
            return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def summary_stats(game_id, fetch=get_json):
    """Read conservative comparable ESPN player lines; ignore unknown schemas."""
    data = fetch(ESPN + "/summary?event=" + urllib.parse.quote(str(game_id)))
    box = (data.get("boxscore") or {}).get("players") or []
    athletes = {}
    for team in box:
        for group in team.get("statistics") or []:
            labels = [str(x).strip().upper() for x in group.get("labels") or []]
            if not ("PTS" in labels and "REB" in labels and "AST" in labels):
                continue
            for item in group.get("athletes") or []:
                person = str((item.get("athlete") or {}).get("id") or "")
                values = item.get("stats") or []
                if not person.isdigit() or len(values) != len(labels):
                    continue
                raw = dict(zip(labels, values))
                pts = stat_line("PTS", raw["PTS"])
                reb = stat_line("REB", raw["REB"])
                ast = stat_line("AST", raw["AST"])
                if pts is None or reb is None or ast is None:
                    continue
                row = {"pts": pts, "reb": reb, "ast": ast}
                for label, names in (("FG", ("fgm", "fga")),
                                     ("3PT", ("threePm", "threePa")),
                                     ("FT", ("ftm", "fta"))):
                    value = stat_line(label, raw.get(label))
                    if isinstance(value, tuple):
                        row.update(zip(names, value))
                athletes[person] = row
    return athletes


def compare_finals(finals, published, fetch=get_json, slot=None):
    missing = sorted(set(finals) - set(published))
    changed = []
    for gid, scores in finals.items():
        prior = published.get(gid)
        if prior and scores not in prior["scores"]:
            changed.append(gid + ":final_score")
    # Rotate a small slice of already-published finals, rather than fetching
    # dozens or hundreds of ESPN summaries every 15 minutes.
    existing = sorted(set(finals) & set(published) - {x.split(":")[0] for x in changed})
    if existing:
        slot = int(time.time() // 900) if slot is None else slot
        count = min(SUMMARY_LIMIT, len(existing))
        start = (slot * count) % len(existing)
        selected = (existing + existing)[start:start + count]
        for gid in selected:
            try:
                current = summary_stats(gid, fetch=fetch)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                print("WARNING: ESPN summary deferred", gid, str(exc), flush=True)
                continue
            known = published[gid]["athletes"]
            matches = 0
            differs = False
            for pid, row in current.items():
                if pid not in known:
                    continue
                common = set(row) & set(known[pid])
                if not {"pts", "reb", "ast"}.issubset(common):
                    continue
                matches += 1
                if any(row[field] != known[pid][field] for field in common):
                    differs = True
                    break
            if differs and matches >= 1:
                changed.append(gid + ":box_correction")
    return missing, changed


def dispatch_allowed(repository, token, fetch=get_json, now=None):
    if not repository or not token:
        raise ValueError("GitHub repository/token missing; cannot dispatch")
    now = now or dt.datetime.now(dt.timezone.utc)
    url = API + "/repos/" + repository + "/actions/workflows/daily-update.yml/runs?per_page=35"
    runs = (fetch(url, token=token) or {}).get("workflow_runs") or []
    for run in runs:
        if run.get("head_branch") != "main":
            continue
        if run.get("status") in ("queued", "in_progress", "waiting", "pending", "requested"):
            return False, "Existing full refresh pending/running"
        if run.get("event") != "workflow_dispatch":
            continue
        created = run.get("created_at")
        if not created:
            continue
        age = (now - dt.datetime.fromisoformat(created.replace("Z", "+00:00"))).total_seconds() / 60
        if 0 <= age < COOLDOWN_MINUTES:
            return False, "Adaptive refresh cooldown (%.0f min remaining)" % (COOLDOWN_MINUTES - age)
    return True, "Clear to dispatch"


def dispatch_refresh(repository, token):
    url = API + "/repos/" + repository + "/actions/workflows/daily-update.yml/dispatches"
    payload = json.dumps({"ref": "main", "inputs": {"season": "2027"}}).encode()
    request = urllib.request.Request(url, data=payload, method="POST", headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
        "User-Agent": "kstate-portal-verified-game-monitor/1.0"
    })
    with urllib.request.urlopen(request, timeout=15) as response:
        if response.status != 204:
            raise RuntimeError("Unexpected workflow dispatch response: %s" % response.status)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dispatch", action="store_true", help="Actually queue validated full refresh")
    parser.add_argument("--date", help="Chicago date, YYYY-MM-DD (testing only)")
    args = parser.parse_args()
    today = dt.date.fromisoformat(args.date) if args.date else dt.datetime.now(CHICAGO).date()
    # Calendar boundaries are deliberate: guard against accidental 2028+ data.
    if not (dt.date(2026, 11, 1) <= today <= dt.date(2027, 4, 30)):
        print("Not 2026-27 game-monitor season; no checks or dispatch")
        return 0
    published = load_published()
    finals = final_games(today)
    missing, changed = compare_finals(finals, published)
    print("ESPN final-game check: %d recent finals; %d already published; %d missing; %d corrected" %
          (len(finals), len(set(finals) & set(published)), len(missing), len(changed)))
    print("Game IDs requiring attention: " + (", ".join(missing + changed) or "none"))
    if not missing and not changed:
        print("NO CHANGE: Full NIL/game pipeline not needed")
        return 0
    if not args.dispatch:
        print("DRY RUN: Would consider dispatching the existing validated full refresh")
        return 0
    token = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
    repo = os.getenv("GITHUB_REPOSITORY")
    allowed, reason = dispatch_allowed(repo, token)
    print("Dispatch gate: " + reason)
    if not allowed:
        return 0
    dispatch_refresh(repo, token)
    print("DISPATCHED: Existing full workflow will independently validate and publish data")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
        print("MONITOR FAILED SAFELY: " + str(error), file=sys.stderr)
        sys.exit(1)
