#!/usr/bin/env python3
"""ESPN historical team-season schedules from archived Division I player-game logs.

For a player with a recorded appearance on a given team and season, missing
team games may be shown as DNP. This does not certify game-by-game enrollment.
No fictitious individual box-score statistics are generated.
"""
import csv,gzip,json
from collections import defaultdict,Counter
from pathlib import Path
ROOT=Path("research_data/historical/game_logs")
OUT=Path("research_data/staged/portal_team_schedules")
OUT.mkdir(parents=True,exist_ok=True)
MOD=64
# [season,gameId,date,teamId,oppTeamId,oppName,homeAway,teamScore,oppScore]
FIELDS=["season","gameId","date","teamId","opponentTeamId","opponent","homeAway","teamScore","opponentScore"]
all_team_games={}
games_to_teams=defaultdict(dict)
ambiguous=[]
def txt(v):return str(v or "").strip()
def number(v):
    try:
        x=float(v)
        return int(x) if x.is_integer() else round(x,2)
    except (ValueError,TypeError):return None
for year in range(2020,2027):
    seen=set()
    source=ROOT/f"player_game_logs_{year}.csv.gz"
    with gzip.open(source,"rt",encoding="utf-8",newline="") as f:
        for row in csv.DictReader(f):
            game=txt(row["game_id"])
            team=txt(row["team_id"])
            pid=txt(row["athlete_id"])
            if not game or not team or not pid:raise ValueError("Missing game/team/player identity")
            key=(year,game,team)
            rec=[year,game,txt(row.get("game_date")),team,txt(row.get("opponent_team_id")),txt(row.get("opponent_team")),txt(row.get("home_away")),
                 number(row.get("team_score")),number(row.get("opponent_score"))]
            if key not in all_team_games:
                all_team_games[key]=rec
            else:
                prev=all_team_games[key]
                # Preserve first known factual value; fills gaps in sparse ESPN metadata
                for pos in range(2,len(rec)):
                    if prev[pos] in ("",None) and rec[pos] not in ("",None):
                        prev[pos]=rec[pos]
                    elif pos in (7,8) and prev[pos] is not None and rec[pos] is not None and prev[pos]!=rec[pos]:
                        if len(ambiguous)<20:ambiguous.append((key,pos,prev[pos],rec[pos]))
            games_to_teams[(year,game)][team]=txt(row.get("team_name"))
assert not ambiguous,("Contradictory per-game scores:",ambiguous)
# Supplement missing opponent identity from the other DI team's exact game ID
for (year,game,team),rec in all_team_games.items():
    other=[(k,name) for k,name in games_to_teams[(year,game)].items() if k!=team]
    if len(other)==1:
        if not rec[4]:rec[4]=other[0][0]
        if not rec[5]:rec[5]=other[0][1]
    if not rec[4] and not rec[5]:
        raise ValueError(f"No opponent identity for game {year} {game} {team}")
sets=[defaultdict(list) for _ in range(MOD)]
season_count=Counter()
for key,rec in all_team_games.items():
    year,game,team=key
    assert team.isdigit(),team
    sets[int(team)%MOD][f"{year}:{team}"].append(rec)
    season_count[year]+=1
for i,schedule in enumerate(sets):
    for entries in schedule.values():entries.sort(key=lambda r:(r[2] or "",r[1]),reverse=True)
    (OUT/f"teams_{i:02d}.json").write_text(json.dumps({"schemaVersion":1,"modulo":MOD,"shard":i,"fields":FIELDS,"teams":schedule},separators=(",",":"),ensure_ascii=False))
manifest={"schemaVersion":1,"modulo":MOD,"shards":MOD,"seasons":list(range(2020,2027)),
          "teamGamesBySeason":dict(season_count),"totalTeamGames":sum(season_count.values()),
          "definition":"All archived played team-games, keyed by exact season and ESPN team ID; DNP is derived when a player appeared for the team that season but has no matching appearance for a team game.",
          "caution":"Season-team membership is based on recorded games, not confirmed roster status on each historical date."}
(OUT/"manifest.json").write_text(json.dumps(manifest,indent=2))
assert manifest["totalTeamGames"]>70000,manifest
print(json.dumps(manifest,indent=2))
