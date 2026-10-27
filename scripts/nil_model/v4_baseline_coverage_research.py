#!/usr/bin/env python3
"""Read-only audit of direct V4 prices versus current roster or site anchor."""
import argparse
import json
from pathlib import Path

def audit(v4, site=None, roster=None):
    if v4.get("model") != "V4_VERIFIED" or v4.get("season") != 2027:
        raise ValueError("Verified V4 baseline is required")
    prices = v4.get("byESPNId") or {}
    if not prices or any(not str(pid).isdigit() or not isinstance(value, (int, float)) or value <= 0
                         for pid, value in prices.items()):
        raise ValueError("Invalid ESPN ID or V4 price")
    s = (site or {}).get("byESPNId") or {}
    roster_ids = {str(x.get("espnAthleteId")) for x in (roster or {}).get("players", [])
                  if str(x.get("espnAthleteId")).isdigit()}
    matches = [pid for pid in prices if pid in s]
    matching_money = [pid for pid in matches if (s[pid]["value"] if isinstance(s[pid], dict) else s[pid]) == prices[pid]]
    return {"verifiedV4": len(prices), "existingSiteAnchorCount": len(s) if site else None,
            "verifiedV4AlsoInSite": len(matches) if site else None,
            "identicalV4AndSitePrices": len(matching_money) if site else None,
            "rosterPlayers": len(roster_ids) if roster else None,
            "rosterWithDirectV4": len(roster_ids & set(prices)) if roster else None,
            "rosterWithoutDirectV4": len(roster_ids - set(prices)) if roster else None,
            "allowNationalPublish": bool(roster_ids and len(roster_ids - set(prices)) == 0
                                         and len(roster_ids) >= 4000),
            "missingV4HasNoInventedFallback": True}

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--v4", required=True)
    p.add_argument("--site-anchor")
    p.add_argument("--roster")
    p.add_argument("--out", required=True)
    args = p.parse_args()
    read = lambda path: json.loads(Path(path).read_text()) if path else None
    result = audit(read(args.v4), read(args.site_anchor), read(args.roster))
    Path(args.out).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
