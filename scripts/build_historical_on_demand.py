#!/usr/bin/env python3
"""Research-only: shard 2020-22 ESPN season box statistics for lazy Portal history."""
from pathlib import Path
import csv,gzip,json
src=Path("research_data/staged/player_seasons_2020_2026.csv.gz")
out=Path("research_data/staged/history_shards")
out.mkdir(parents=True,exist_ok=True)
numeric=["gp","gs","minutes","mpg","pts","ppg","reb","rpg","ast","apg","stl","spg","blk","bpg","tov","topg","pf","fgm","fga","fg_pct","two_pm","two_pa","two_pt_pct","three_pm","three_pa","three_pt_pct","ftm","fta","ft_pct","oreb","dreb","efg_pct","ts_pct","ast_to"]
shards=[{} for _ in range(16)]
counts={2020:0,2021:0,2022:0}
def number(s):
    if s is None or s=="":return None
    try:
        v=float(s)
        return int(v) if v.is_integer() else round(v,9)
    except (TypeError,ValueError):return None
with gzip.open(src,"rt",encoding="utf8",newline="") as f:
    for row in csv.DictReader(f):
        try:
            year=int(row["season"])
            ident=str(int(row["athlete_id"]))
        except (TypeError,ValueError):continue
        if year not in counts:continue
        counts[year]+=1
        r={"season":year,"seasonLabel":row.get("season_label"),"team":row.get("team_name"),"teamId":row.get("team_id"),"name":row.get("player_name")}
        for key in numeric:r[key]=number(row.get(key))
        shards[int(ident)%16].setdefault(ident,[]).append(r)
assert counts=={2020:4796,2021:5020,2022:5090},counts
for i,people in enumerate(shards):
    for rows in people.values():rows.sort(key=lambda x:x["season"])
    (out/f"history_2020_2022_{i:02d}.json").write_text(json.dumps({"schemaVersion":1,"seasons":[2020,2021,2022],"shard":i,"players":people},separators=(",",":"),ensure_ascii=False))
print(json.dumps({"status":"PASS","sourceCounts":counts,"shards":len(shards),"players":len({k for x in shards for k in x})}))
