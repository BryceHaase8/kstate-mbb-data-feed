#!/usr/bin/env python3
"""Fail-closed GitHub publication QA for ESPN player-season statistics."""
import csv,io,json,subprocess,sys,datetime
from collections import Counter,defaultdict
from pathlib import Path
DATA=Path("data/current_player_season_stats.csv")
PUBLIC=Path("public/portal_factual_data.json")
QA=Path("public/portal_factual_qa.json")
def parse(text):
    reader=csv.DictReader(io.StringIO(text))
    cols={"season","athlete_id","team_id","gp","pts","fga","fgm","three_pa","three_pm","reb","ast","minutes"}
    if not cols.issubset(reader.fieldnames or []):raise ValueError("Missing ESPN factual fields")
    result={};counts=Counter();teams=defaultdict(set)
    for r in reader:
        y=int(r["season"]);p=r["athlete_id"].strip();t=r["team_id"].strip()
        if y<2023 or y>2027 or not p.isdigit() or not t.isdigit():raise ValueError("Invalid player/team/season")
        key=(y,p)
        if key in result:raise ValueError("Duplicate player-season "+str(key))
        for f in ("gp","pts","fga","fgm","three_pa","three_pm","reb","ast","minutes"):
            v=float(r[f] or 0)
            if v<0 or v>100000:raise ValueError("Bad basketball stat "+str(key)+f)
        if float(r["fgm"] or 0)>float(r["fga"] or 0)+.01 or float(r["three_pm"] or 0)>float(r["three_pa"] or 0)+.01:
            raise ValueError("Makes exceed attempts: "+str(key))
        result[key]=r;counts[y]+=1;teams[y].add(t)
    return result,counts,teams
def same(a,b):
    if not b:return False
    for k,v in a.items():
        x=b.get(k)
        if x==v:continue
        try:
            if v not in ("",None) and x not in ("",None):
                m,n=float(v),float(x)
                if abs(m-n)<=max(1e-9,max(abs(m),abs(n))*1e-10):continue
        except (ValueError,TypeError):pass
        return False
    return True
def run():
    current,counts,teams=parse(DATA.read_text())
    old,previous,_=parse(subprocess.check_output(["git","show","HEAD:data/current_player_season_stats.csv"],text=True))
    last=max(counts)
    if last not in (2026,2027) or last<max(previous):raise ValueError("Unexpected active season")
    for y in range(2023,2027):
        if counts[y]<4000:raise ValueError("Missing historic season "+str(y))
    if last==2027 and counts[last]<20:raise ValueError("Too little active-season data to publish")
    for key,row in old.items():
        if key[0]<last and not same(row,current.get(key)):
            raise ValueError("Historical record altered "+str(key))
    if last in previous and counts[last]<previous[last]*.92:
        raise ValueError("Active season coverage collapsed")
    feed=json.loads(PUBLIC.read_text())
    players=feed.get("players") or {}
    unique=len({pid for _,pid in current})
    if feed.get("schemaVersion")!=2 or feed.get("latestSeason")!=last or feed.get("playerSeasonCount")!=len(current) or feed.get("playerCount")!=unique or len(players)!=unique:
        raise ValueError("CSV/JSON count or schema mismatch")
    for (year,pid) in current:
        player=players.get(pid)
        if not player or not any(int(x.get("season") or 0)==year for x in player.get("seasons",[])):
            raise ValueError("Missing player ID in public feed "+pid)
    for y,c in counts.items():
        if int(feed.get("seasonPlayerCounts",{}).get(str(y),-1))!=c:
            raise ValueError("Season count mismatch "+str(y))
    stage=("EARLY_SEASON_PARTIAL" if last==2027 and
           (counts[last]<4000 or len(teams[last])<300) else
           "2026_27_IN_SEASON" if last==2027 else "2025_26_ARCHIVE")
    report={"schemaVersion":1,"generatedAt":datetime.datetime.now(datetime.timezone.utc).isoformat(),
      "status":"PASS","currentDataSeason":last,"currentDataStage":stage,
      "seasonPlayerCounts":{str(y):counts[y] for y in sorted(counts)},
      "playerSeasonCount":len(current),"playerCount":unique,
      "currentSeasonTeamsWithGames":len(teams[last]),
      "modelGuard":{"impactSeason":2026,"nilV4Season":2026,"percentileSeason":2026,"modelsRecomputed":False},
      "statsAreNotRosterMembership":True,"historicalPreservation":"PASS",
      "staffGoogleSheetsUntouched":True}
    QA.write_text(json.dumps(report,indent=2)+"\n")
    print("ESPN factual publication QA PASS",json.dumps({"season":last,"stage":stage,"players":counts[last]}))
if __name__=="__main__":
    try:run()
    except Exception as e:
        print("PUBLICATION BLOCKED:",str(e),file=sys.stderr)
        sys.exit(1)
