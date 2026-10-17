#!/usr/bin/env python3
"""Polite, resilient bulk Torvik team-strength ingestion (RESEARCH ONLY).

Prefers the published season JSON, falls back to the documented CSV only if the
JSON is missing or not parseable. Refuses to retry HTTP 403 (access denial).
Never overwrites the last verified snapshot with error pages/partial data.
Python stdlib only. Doesn't touch public Portal data or RAPM coefficients.
"""
import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import re
import sys
import time
import unicodedata
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

UA = "Mozilla/5.0 (compatible; KStateMBBAnalytics/1.0; one daily published bulk-file request)"
RETRYABLE = {408, 429, 500, 502, 503, 504}
MAX_BYTES = 3_000_000
# Headerless JSON indices verified against 2026 team-results CSV.
NAMES = ("rank", "team", "conf", "record", "adjoe", "adjde", "barthag", "adjt")
INDEX = dict(rank=0, team=1, conf=2, record=3, adjoe=4, adjde=6,
             barthag=8, adjt=44)
ALIASES = {
    "Miami FL": "Miami Hurricanes", "Miami OH": "Miami OH",
    "Connecticut": "UConn", "Illinois Chicago": "UIC",
    "McNeese St.": "McNeese", "Long Island": "LIU",
    "N.C. A&T": "North Carolina A&T", "N.C. Central": "North Carolina Central",
    "Arkansas Little Rock": "Little Rock",
    "Penn": "Penn Quakers"
}

def utcnow():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def normalize(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    s = s.replace("&", " and ").replace("'", "")
    s = re.sub(r"^st[.]?\s+", "saint ", s)
    s = re.sub(r"\bst\.", "state", s)
    return re.sub(r"\s+", " ", re.sub("[^a-z0-9]+", " ", s)).strip()

def parse_payload(payload, fmt):
    data = []
    if fmt == "json":
        raw = json.loads(payload.decode("utf-8-sig"))
        if not isinstance(raw, list):
            raise ValueError("Expected JSON array of team arrays")
        for r in raw:
            if not isinstance(r, list) or len(r) != 45:
                raise ValueError("JSON row is not the expected 45-column schema")
            data.append(r)
    elif fmt == "csv":
        rows = list(csv.reader(io.StringIO(payload.decode("utf-8-sig"))))
        if not rows or len(rows[0]) != 45 or rows[0][:4] != ["rank", "team", "conf", "record"]:
            raise ValueError("CSV headers do not match the Torvik team-results layout")
        if rows[0][4].strip().lower() != "adjoe" or rows[0][6].strip().lower() != "adjde":
            raise ValueError("CSV adjusted efficiency header mismatch")
        if rows[0][44].strip().lower() != "adjt":
            raise ValueError("CSV adjusted tempo header mismatch")
        for row in rows[1:]:
            if len(row) != 45:
                raise ValueError("CSV row is not the expected 45-column schema")
            data.append(row)
    else:
        raise ValueError("Unknown format")
    if not 340 <= len(data) <= 400:
        raise ValueError("Unexpected number of teams")
    result = []
    for i, r in enumerate(data):
        try:
            rank = int(r[0]); team = str(r[1]).strip(); conf = str(r[2]).strip()
            record = str(r[3]).strip()
            oe = float(r[4]); de = float(r[6])
            b = float(r[8]); pace = float(r[44])
            if not team or not conf or not re.fullmatch(r"\d+-\d+", record):
                raise ValueError("empty name/conference or unexpected record")
            if not (1 <= rank <= 400 and 65 <= oe <= 155 and 65 <= de <= 140
                    and 0 <= b <= 1 and 50 <= pace <= 90):
                raise ValueError("out-of-range numeric value")
            result.append({"torvikTeam": team, "conference": conf, "record": record,
                 "rank": rank, "adjOE": round(oe, 6), "adjDE": round(de, 6),
                 "adjEM": round(oe-de, 6), "barthag": round(b, 8),
                 "adjTempo": round(pace, 6), "espnTeamId": None})
        except (ValueError, IndexError, TypeError) as e:
            raise ValueError("Invalid Torvik team row %d: %s" % (i, e)) from e
    if len(set(x["torvikTeam"] for x in result)) != len(result):
        raise ValueError("Duplicate Torvik team names")
    if len(set(x["rank"] for x in result)) != len(result):
        raise ValueError("Duplicate Torvik ranks")
    return result

def espn_crosswalk(teams, context_path, season):
    context = json.loads(Path(context_path).read_text())
    seasons = context["teams"]
    if not seasons:
        raise ValueError("Empty ESPN team context")
    # 2027 preseason: use latest available ESPN school directory, not future games.
    source_season = str(season) if str(season) in seasons else str(max(map(int, seasons)))
    available = seasons[source_season]
    torvik_names = {}
    for r in teams:
        base = ALIASES.get(r["torvikTeam"], r["torvikTeam"])
        torvik_names[r["torvikTeam"]] = normalize(base)
    match_candidates = {}
    for eid, e in available.items():
        ename = normalize(e["name"])
        candidates = [(len(q), source) for source, q in torvik_names.items()
                      if ename == q or ename.startswith(q + " ")]
        if candidates:
            best = max(c[0] for c in candidates)
            winners = [s for l,s in candidates if l == best]
            if len(winners) == 1:
                match_candidates.setdefault(winners[0], []).append(str(eid))
    ambiguous, missing, mapped = [], [], 0
    for r in teams:
        ids = match_candidates.get(r["torvikTeam"], [])
        if len(ids) == 1:
            r["espnTeamId"] = ids[0]; mapped += 1
        elif len(ids) > 1:
            ambiguous.append({"team":r["torvikTeam"],"possibleESPNIDs":ids})
        else:
            missing.append(r["torvikTeam"])
    return mapped, missing, ambiguous, source_season

class AccessDenied(Exception):
    pass

def http_get(url, attempts=3):
    last = None
    for n in range(attempts):
        req = Request(url, headers={"User-Agent":UA, "Accept":"application/json,text/csv,*/*"})
        try:
            with urlopen(req, timeout=24) as response:
                value = response.read(MAX_BYTES + 1)
                if len(value) > MAX_BYTES:
                    raise ValueError("Unusually large Torvik response")
                ct = (response.headers.get("Content-Type") or "").lower()
                if "html" in ct or value.lstrip().startswith(b"<"):
                    raise ValueError("Received HTML rather than data")
                return value
        except HTTPError as ex:
            if ex.code == 403:
                raise AccessDenied("HTTP 403 from Torvik/CDN: do not retry access denial") from ex
            if ex.code not in RETRYABLE:
                raise
            last = ex
        except (URLError, TimeoutError) as ex:
            last = ex
        if n < attempts - 1:
            wait = min(4 * (2 ** n), 12)
            print("Temporary HTTP/network failure; retrying in %s seconds" % wait)
            time.sleep(wait)
    raise RuntimeError("Torvik bulk download failed after bounded retries: %s" % last)

def write_json(path, obj):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(obj, indent=2) + "\n")
    temp.replace(path)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--snapshot", default=None)
    parser.add_argument("--status", default=None)
    parser.add_argument("--espn-context", default="public/research_team_context.json")
    parser.add_argument("--fixture", default=None, help="Local JSON or CSV test input; skips network")
    args = parser.parse_args()
    season = args.season
    snap = Path(args.snapshot or "research_qa/torvik_team_strength_%d.json" % season)
    stat = Path(args.status or "research_qa/torvik_team_strength_%d_status.json" % season)
    prefix = "https://barttorvik.com/%d_team_results." % season
    urls = [("json", prefix+"json"), ("csv", prefix+"csv")]
    existing = None
    if snap.is_file():
        try:
            v = json.loads(snap.read_text())
            if v.get("season") == season and len(v.get("teams",[])) >= 340:
                existing = v
        except (ValueError, OSError):
            pass
    failures = []
    fresh = None
    options = [(Path(args.fixture).suffix.lstrip(".").lower(), args.fixture)] if args.fixture else urls
    for fmt, location in options:
        if fmt not in ("json","csv"):
            raise ValueError("Fixture must end in .json or .csv")
        try:
            raw = Path(location).read_bytes() if args.fixture else http_get(location)
            teams = parse_payload(raw, fmt)
            mapped, missing, ambiguous, context_season = espn_crosswalk(teams, args.espn_context, season)
            if mapped < len(teams)*0.90:
                raise ValueError("ESPN crosswalk fell below 90%%: %d / %d" % (mapped, len(teams)))
            newhash = hashlib.sha256(raw).hexdigest()
            stage = "PRESEASON_PROJECTION" if all(t["record"]=="0-0" for t in teams) else "IN_SEASON_OR_FINAL"
            fetched = utcnow()
            same = existing and existing.get("sourceSha256")==newhash
            if same:
                fresh = existing
                print("Source unchanged: retaining previously verified snapshot")
            else:
                fresh = {"schemaVersion":2,"season":season,"source":"Torvik published bulk team-results",
                  "sourceUrl":prefix+fmt,"sourceFormat":fmt,"sourceSha256":newhash,
                  "retrievedAtUTC":fetched,"ratingsStage":stage,"teamCount":len(teams),
                  "matchedESPNTeams":mapped,"crosswalkESPNSchoolYear":int(context_season),
                  "unmatchedTeams":missing,"ambiguousTeams":ambiguous,"teams":teams}
                write_json(snap, fresh)
            result = {"status":"ok","checkedAtUTC":fetched, "season":season, "dataAgeHours":0,
                      "sourceFormat":fmt,"sourceSha256":newhash,"teamCount":len(teams),
                      "espnMatched":mapped,"unmatched":missing,"ambiguous":ambiguous,
                      "sourceUnchanged":bool(same),"ratingsStage":stage}
            write_json(stat,result)
            print("Validated",len(teams),"teams,",mapped,"ESPN matches; stage",stage)
            return 0
        except AccessDenied as ex:
            failures.append({"format":fmt,"cause":"access_denied_403"})
            print("BLOCKED:",str(ex),file=sys.stderr)
            break  # Do not hammer the other endpoint under a CDN access denial.
        except (HTTPError, URLError, ValueError, RuntimeError, OSError, json.JSONDecodeError) as ex:
            failures.append({"format":fmt,"cause":type(ex).__name__,"message":str(ex)[:240]})
            print("Fetch failed (%s): %s" % (fmt,ex),file=sys.stderr)
            # CSV is a documented alternative to malformed/missing JSON, but only
            # after a normal failure. Never switch hosts or defeat a 403.
    age = None
    if existing:
        try:
            age = round((dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat(
                existing["retrievedAtUTC"])).total_seconds()/3600,2)
        except (ValueError, KeyError):
            pass
    status = "stale_fallback" if existing else "unavailable"
    write_json(stat,{"status":status,"season":season,"checkedAtUTC":utcnow(),
           "lastGoodRetrievedAtUTC":existing.get("retrievedAtUTC") if existing else None,
           "lastGoodAgeHours":age,"failures":failures,
           "note":"Last verified snapshot preserved; no new team ratings published."})
    print("WARNING: status =",status,"last_good_age_hours =",age,file=sys.stderr)
    return 0 if existing else 3

if __name__=="__main__":
    sys.exit(main())
