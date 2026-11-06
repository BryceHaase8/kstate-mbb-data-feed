#!/usr/bin/env python3
"""Read-only exact-ESPN-ID national NIL coverage audit: roster + verified games.

A NIL model with all values nonblank may still omit active players entirely.
No player is assigned a fabricated estimate by this audit.
"""
import argparse
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def read(path):return json.loads(Path(path).read_text(encoding="utf-8"))

def audit(model=None):
    prices=read(model or ROOT/"public/nil_estimation_model_2027.json")["byESPNId"]
    roster=read(ROOT/"data/roster_2027_advanced.json")
    roster_ids={str(row[0]):row for row in roster["players"]}
    blanks=[id for id,row in prices.items()
            if not isinstance(row.get("preseason"),(int,float))
            or not isinstance(row.get("value"),(int,float))]
    no_roster=[{"id":id,"name":row[1],"teamId":row[2]}
               for id,row in roster_ids.items() if id not in prices]
    played={}
    shards=0
    for index in range(128):
        path=ROOT/"public/portal_game_logs_2027"/("games_%03d.json"%index)
        if not path.is_file():raise ValueError("Missing player game-log shard "+path.name)
        shard=read(path);shards+=1
        fields=shard.get("fields") or [];team_idx=fields.index("team")
        for id,lines in (shard.get("players") or {}).items():
            if lines:
                p=played.setdefault(str(id),{"team":lines[0][team_idx],"games":0})
                p["games"]+=len(lines)
    no_games=[{"id":id,**info} for id,info in sorted(played.items()) if id not in prices]
    report={"modelPlayers":len(prices),"rosterPlayers":len(roster_ids),
            "verifiedPlayersWithGames":len(played),"gameLogShardsChecked":shards,
            "missingPreseasonOrNILAmount":len(blanks),
            "rosterPlayersWithoutNIL":len(no_roster),
            "playedPlayersWithoutNIL":len(no_games),
            "blankESPNIDs":blanks[:100],
            "rosterMissing":no_roster[:100],"playedMissing":no_games[:100]}
    print("NIL COVERAGE 2027",json.dumps(report,indent=2),flush=True)
    return report

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--model")
    parser.add_argument("--strict",action="store_true")
    args=parser.parse_args();r=audit(args.model)
    if args.strict and any(r[k] for k in ("missingPreseasonOrNILAmount","rosterPlayersWithoutNIL","playedPlayersWithoutNIL")):
        raise SystemExit("Missing verified player valuations")
