#!/usr/bin/env python3
"""Prepare ESPN box-score game logs as on-demand player-ID assets.
Research-only: no model coefficients, staff data, or production changes.
The files are generated from archived real player-game records, never PBP lineups.
"""
from pathlib import Path
import csv, gzip, json, math
from collections import defaultdict, Counter

ROOT=Path("research_data/historical/game_logs")
OUT=Path("research_data/staged/portal_game_logs")
OUT.mkdir(parents=True,exist_ok=True)
MOD=128
KEYS=["season","gameId","date","team","opponent","homeAway","teamScore",
      "opponentScore","started","minutes","pts","reb","ast","stl",
      "blk","tov","pf","fgm","fga","threePm","threePa","ftm","fta",
      "oreb","dreb"]
shards=[defaultdict(list) for _ in range(MOD)]
count=Counter()
teams=Counter()
def n(v):
    if v is None or str(v).strip()=="":
        return None
    try:
        x=float(v)
        if not math.isfinite(x):return None
        return int(x) if x.is_integer() else round(x,2)
    except (ValueError,TypeError):
        return None
def s(v):
    return str(v or "").strip() or None
def b(v):
    x=str(v or "").strip().lower()
    return 1 if x in ("true","t","1","yes") else 0
for season in range(2020,2027):
    source=ROOT/f"player_game_logs_{season}.csv.gz"
    assert source.exists(),f"Missing verified archive: {source}"
    with gzip.open(source,"rt",encoding="utf-8",newline="") as f:
        seen=set()
        for r in csv.DictReader(f):
            pid=s(r.get("athlete_id"))
            game=s(r.get("game_id"))
            team=s(r.get("team_id"))
            if not pid or not pid.isdigit() or not game or not team:
                raise ValueError(f"Missing exact player/game/team ID in {season}")
            if str(r.get("season"))!=str(season):
                raise ValueError("Incorrect archive season")
            key=(game,team,pid)
            if key in seen:raise ValueError(f"Duplicate player-game: {key}")
            seen.add(key)
            item=[season,game,s(r.get("game_date")),s(r.get("team_name")),
                  s(r.get("opponent_team")),s(r.get("home_away")),
                  n(r.get("team_score")),n(r.get("opponent_score")),
                  b(r.get("started")),n(r.get("minutes")),n(r.get("points")),
                  n(r.get("rebounds")),n(r.get("assists")),n(r.get("steals")),
                  n(r.get("blocks")),n(r.get("turnovers")),n(r.get("fouls")),
                  n(r.get("fgm")),n(r.get("fga")),n(r.get("three_pm")),
                  n(r.get("three_pa")),n(r.get("ftm")),n(r.get("fta")),
                  n(r.get("offensive_rebounds")),n(r.get("defensive_rebounds"))]
            assert len(item)==len(KEYS)
            shards[int(pid)%MOD][pid].append(item)
            count[season]+=1
            teams[season]+=(0 if not team else 1)
    assert 80_000<count[season]<140_000,(season,count[season])
for i,rows in enumerate(shards):
    for pid,player_games in rows.items():
        player_games.sort(key=lambda r:(r[2] or "",r[1]),reverse=True)
    payload={"schemaVersion":1,"shard":i,"modulo":MOD,"fields":KEYS,"players":rows}
    (OUT/f"games_{i:03d}.json").write_text(json.dumps(payload,separators=(",",":"),ensure_ascii=False))
manifest={"schemaVersion":1,"seasons":list(range(2020,2027)),
    "source":"Archived ESPN Division I player-game box scores, research QA",
    "modulo":MOD,"totalPlayerGames":sum(count.values()),
    "playerGamesByYear":dict(count),"uniquePlayers":len({p for sh in shards for p in sh}),
    "files":MOD}
assert manifest["totalPlayerGames"]>700_000
(OUT/"manifest.json").write_text(json.dumps(manifest,indent=2))
print(json.dumps(manifest,indent=2))
