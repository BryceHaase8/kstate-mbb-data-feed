#!/usr/bin/env python3
"""Build complete ESPN-ID keyed 2023-2026 game scouting history; never guess identities."""
import csv,json,datetime,pathlib,collections,math
source=pathlib.Path("data/current_player_season_stats.csv")
out=pathlib.Path("research_data/staged/games_authoritative_history_2023_2026.json")
qa=pathlib.Path("research_qa/games/games_espn_identity_history_qa.json")
rows={};counts=collections.Counter();byname=collections.defaultdict(set);bad=0
def n(s): 
 try:
  v=float(s)
  return round(v,4) if math.isfinite(v) else None
 except (TypeError,ValueError):return None
with source.open(newline="",encoding="utf-8-sig") as fp:
 for r in csv.DictReader(fp):
  year=int(r.get("season") or 0)
  if year not in (2023,2024,2025,2026):continue
  pid=str(r.get("athlete_id") or "").strip()
  team=str(r.get("team_id") or "").strip()
  if not pid.isdecimal() or not team.isdecimal():bad+=1;continue
  gp=n(r.get("gp")) or 0
  if gp<=0:continue
  key=(pid,year)
  if key in rows:raise ValueError("Duplicate athlete+season: "+repr(key))
  name=str(r.get("player_name") or "").strip()
  school=str(r.get("team_name") or "").strip()
  if not name or not school:bad+=1;continue
  stats=[team,n(r.get("ppg")),n(r.get("rpg")),n(r.get("apg")),n(r.get("mpg")),
         n(r.get("efg_pct")),n(r.get("ts_pct")),int(gp),name,school,str(r.get("position") or "").strip()]
  rows[key]=stats;counts[year]+=1
  if year==2026:byname[name.casefold()].add(pid)
assert all(counts[y]>=4000 for y in (2023,2024,2025,2026)),counts
players=collections.defaultdict(dict)
for (pid,year),row in rows.items():players[pid][str(year)]=row
payload={"schemaVersion":2,"source":"GitHub validated ESPN/hoopR 2023-26 season totals; keyed by athlete_id",
         "latestSeason":2026,"generatedAt":datetime.datetime.now(datetime.timezone.utc).isoformat(),
         "seasonCounts":{str(y):counts[y] for y in sorted(counts)},"players":dict(players)}
out.parent.mkdir(parents=True,exist_ok=True);qa.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(payload,separators=(",",":"),ensure_ascii=False))
def sample(pid):return players.get(pid,{})
report={"status":"PASS","ESPNIds":len(players),"seasonCounts":{str(y):counts[y] for y in counts},
        "rows":len(rows),"badRows":bad,"unambiguous2026Names":sum(len(z)==1 for z in byname.values()),
        "ambiguous2026Names":sum(len(z)>1 for z in byname.values()),
        "WilliamBerg_5105857":sample("5105857"),
        "DukeCameron_5210407":sample("5210407"),
        "PortlandCameron_5314723":sample("5314723"),
        "safety":"No player matches by name. This file is ESPN athlete-ID keyed only."}
qa.write_text(json.dumps(report,indent=2))
assert "2026" in players.get("5105857",{}),"Will Berg expected in 2026 full feed"
print(json.dumps(report))
