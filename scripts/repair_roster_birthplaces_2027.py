#!/usr/bin/env python3
"""Restore ESPN-verified international birth countries without touching player facts.
Updates staged 2027 roster assets only. Keys are exact ESPN athlete IDs.
"""
import argparse
import concurrent.futures
import copy
import datetime
import json
import os
from pathlib import Path
import threading
import time
import urllib.error
import urllib.request

ROOT = Path("research_data/staged")
REGISTRY = ROOT / "espn_verified_birthplaces_2027.json"
QA = Path("research_qa/roster_integration/espn_birthplace_repair_2027.json")
PRIMARY = ROOT / "roster_2027_fast_ready.json"
ASSETS = (
    "roster_2027_fast_ready.json",
    "roster_2027_zero_fast_ready.json",
    "roster_2027_site_compact.json",
    "roster_2027_site_compact_ready.json",
    "roster_2027_zero_fallback.json",
    "roster_2027_zero_fallback_ready.json",
    "current_roster_2027_candidate.json",
)
_lock = threading.Lock()
_next_request = 0.0


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def clean(v):
    return str(v).strip() if isinstance(v, str) and str(v).strip().upper() not in ("NA", "N/A", "NULL") else ""


def get_city(place):
    value = clean(place)
    return value[:-3].strip().rstrip(",") if value.endswith(" NA") else ""


def resolve(pid, original):
    global _next_request
    # Throttle across worker threads and retry transient ESPN failures.
    url = ("https://sports.core.api.espn.com/v2/sports/basketball/"
           "leagues/mens-college-basketball/athletes/" + pid)
    for attempt in range(5):
        try:
            with _lock:
                delay = max(0.0, _next_request - time.monotonic())
                if delay:
                    time.sleep(delay)
                _next_request = time.monotonic() + 0.34
            request = urllib.request.Request(url, headers={
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0 (compatible; KState-roster-birthplace-review/1.0)"})
            with urllib.request.urlopen(request, timeout=18) as r:
                raw = json.load(r)
            if str(raw.get("id")) != pid:
                return pid, None, "ESPN_ID_MISMATCH"
            birthplace = raw.get("birthPlace") or {}
            if not isinstance(birthplace, dict):
                return pid, None, "NO_ESPN_BIRTHPLACE"
            city = clean(birthplace.get("city"))
            country = clean(birthplace.get("country"))
            state = clean(birthplace.get("state"))
            if not city or city.casefold() != original.casefold():
                return pid, None, "CITY_MISMATCH_OR_MISSING"
            if country and country.casefold() not in ("united states", "united states of america", "usa", "us"):
                proper = f"{city}, {country}"
            elif country:
                proper = f"{city}, {state}" if state else city
            elif state:
                proper = f"{city}, {state}"
            else:
                return pid, None, "NO_COUNTRY_OR_STATE"
            return pid, {"city": city, "country": country, "state": state,
                         "display": proper, "source": "ESPN_CORE_V2_ATHLETE_ID"}, None
        except urllib.error.HTTPError as exc:
            if exc.code in (404, 400):
                return pid, None, f"ESPN_HTTP_{exc.code}"
            if attempt == 4:
                return pid, None, f"ESPN_HTTP_{exc.code}"
        except (OSError, ValueError, TypeError) as exc:
            if attempt == 4:
                return pid, None, type(exc).__name__
        time.sleep(min(14, 1.5 * (attempt + 1) ** 2))
    return pid, None, "RETRIES_EXHAUSTED"


def collect(limit=0):
    primary = load(PRIMARY)
    assert primary.get("schemaVersion") == 3 and primary.get("rosterSeason") == 2027
    all_rows = primary["players"]
    assert len(all_rows) > 5000
    candidates = {}
    for row in all_rows:
        pid = str(row[0])
        city = get_city(row[7])
        if city:
            assert pid.isdigit() and pid not in candidates
            candidates[pid] = city
    register = load(REGISTRY) if REGISTRY.exists() else {
        "schemaVersion": 1, "season": 2027, "byESPNId": {}
    }
    verified = register["byESPNId"]
    to_query = [(pid, city) for pid, city in candidates.items()
                if pid not in verified or
                clean(verified[pid].get("city")).casefold() != city.casefold()]
    if limit:
        to_query = to_query[:limit]
    failures = {}
    successful = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(resolve, pid, city) for pid, city in to_query]
        for i, fut in enumerate(concurrent.futures.as_completed(futures), 1):
            pid, value, error = fut.result()
            if value:
                verified[pid] = value
                successful += 1
            else:
                failures[pid] = error
            if i % 100 == 0:
                print("ESPN country lookup", i, "/", len(to_query),
                      "verified", successful, "unresolved", len(failures), flush=True)
    register["verifiedAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    assert "5311523" in verified and verified["5311523"]["display"] == "Marseille, France", (
        "Kamardine official ESPN birthplace check failed")
    write(REGISTRY, register)
    print("ESPN PLACE SOURCE:", len(candidates), "NA placeholders;", successful,
          "new verified;", len(failures), "unresolved", flush=True)
    return len(candidates), failures


def patch():
    if not REGISTRY.exists():
        print("No verified ESPN country register; keeping existing roster unchanged")
        return {}
    registry = load(REGISTRY)
    assert registry.get("schemaVersion") == 1 and registry.get("season") == 2027
    verified = registry["byESPNId"]
    assert all(str(pid).isdigit() and v.get("source") == "ESPN_CORE_V2_ATHLETE_ID"
               for pid, v in verified.items())
    changes = {}
    touched = {}
    for file in ASSETS:
        path = ROOT / file
        if not path.exists():
            continue
        src = load(path)
        before = copy.deepcopy(src)
        modified = 0
        for row in src.get("players", []):
            if isinstance(row, list):
                pid, old = str(row[0]), row[7]
            else:
                pid, old = str(row["espnAthleteId"]), row.get("birthPlace", "")
            rec = verified.get(pid)
            if not rec or not get_city(old):
                continue
            # No inference: only replace an exact city match for the same ESPN ID.
            if get_city(old).casefold() != rec["city"].casefold():
                continue
            new = rec["display"]
            if isinstance(row, list):
                row[7] = new
            else:
                row["birthPlace"] = new
            changes[pid] = (old, new)
            modified += 1
        # Verify the only semantic changes are to the permitted birthplace field.
        def strip_birth(doc):
            d = copy.deepcopy(doc)
            for row in d.get("players", []):
                if isinstance(row, list):
                    row[7] = None
                else:
                    row["birthPlace"] = None
            return d
        assert strip_birth(src) == strip_birth(before), "Unrelated data modified: " + file
        if modified:
            write(path, src)
        touched[file] = modified
    primary_now = load(PRIMARY)["players"]
    kamardine = [r for r in primary_now if str(r[0]) == "5311523"]
    if kamardine:
        assert kamardine[0][7] == "Marseille, France", (
            "Kamardine verified birthplace not present in primary roster")
    remaining = sum(bool(get_city(r[7])) for r in primary_now)
    report = {"season": 2027, "source": "ESPN official core athlete IDs",
              "confirmedBirthplaces": len(verified), "correctedPlayers": len(changes),
              "remainingNa": remaining, "changedFiles": touched,
              "siteFilesModified": False, "nilValuesModified": False}
    write(QA, report)
    print("BIRTHPLACE REPAIR QA", json.dumps(report), flush=True)
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fetch", action="store_true", help="Query ESPN core for missing states")
    p.add_argument("--apply", action="store_true", help="Patch only birthplace fields")
    p.add_argument("--limit", type=int, default=0)
    args = p.parse_args()
    if args.fetch:
        count, failures = collect(args.limit)
        if not args.limit and len(failures) > count * .4:
            raise RuntimeError("Too many ESPN lookup failures; refusing partial publication")
    if args.apply:
        report = patch()
        if args.fetch and not args.limit and report["correctedPlayers"] < 500:
            raise RuntimeError("Unexpectedly low verified birthplace coverage")


if __name__ == "__main__":
    main()
