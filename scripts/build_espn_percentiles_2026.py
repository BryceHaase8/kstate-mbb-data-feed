#!/usr/bin/env python3
"""Research-only: ESPN 2025-26 player percentiles (five estimated positions).
Inputs: our archived ESPN box/game logs + validated ESPN shot-location shards.
No Bart Torvik player statistics, labels, metrics, targets or model coefficients.
"""
import csv,gzip,json,math,re
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path("research_data")
OUT=ROOT/"staged/portal_percentiles_2026"
OUT.mkdir(parents=True,exist_ok=True)
METRICS=['pts30','efg','ts','ftRate','rim30','mid30','three30','usage','ast30','astPct','astTov','tovPct','stl30','blk30','twoPct','threePct','ftPct','threeRate','two30','reb30','oreb30','dreb30','orebPct','drebPct','stocks30','fta30','fga30']
SHOOT_MIN={'twoPct':50,'threePct':40,'ftPct':30,'efg':100,'ts':100,'ftRate':100,'threeRate':100}
def num(x):
    try:
        if x in ('',None):return None
        x=float(x)
        return x if math.isfinite(x) else None
    except (TypeError,ValueError):return None
def n(r,k):return num(r.get(k))
def div(a,b,k=1):return a*k/b if a is not None and b is not None and b>0 else None
def finite(x):return round(x,4) if x is not None and math.isfinite(x) else None
with gzip.open(ROOT/"historical/season_totals/player_season_2026.csv.gz","rt",encoding="utf8",newline="") as f:
    season=list(csv.DictReader(f))
assert len(season)==5019,len(season)
with gzip.open(ROOT/"historical/game_logs/player_game_logs_2026.csv.gz","rt",encoding="utf8",newline="") as f:
    game_logs=list(csv.DictReader(f))
assert len(game_logs)>110000,len(game_logs)
team=defaultdict(lambda:defaultdict(float))
boxByGame=defaultdict(lambda:defaultdict(float))
for row in season:
    tid=str(row.get("team_id") or "")
    if not tid:continue
    s=team[tid]
    s["gp"]=max(s["gp"],n(row,"gp") or 0)
    for k in ("minutes","fga","fta","tov","fgm","oreb","dreb"):
        s[k]+=n(row,k) or 0
for row in game_logs:
    ident=(str(row.get("game_id") or ""),str(row.get("team_id") or ""))
    v=boxByGame[ident]
    for key,source in (("oreb","offensive_rebounds"),("dreb","defensive_rebounds")):\n        v[key]+=n(row,source) if n(row,source) is not None else (n(row,key) or 0)
# Same-game actual opponents rather than summing all games of an opponent.
oppRebounds=defaultdict(lambda:defaultdict(float))
for shard in range(64):
    doc=json.loads((ROOT/"staged/portal_team_schedules"/f"teams_{shard:02d}.json").read_text())
    for key,events in doc["teams"].items():
        if not key.startswith("2026:"):continue
        tid=key.split(":")[1]
        for event in events:
            other=str(event[4] or "")
            if not other:continue
            opp=boxByGame.get((str(event[1]),other))
            if opp is None:continue
            oppRebounds[tid]["oreb"]+=opp["oreb"]
            oppRebounds[tid]["dreb"]+=opp["dreb"]
currentBio={}
for athlete in json.loads((ROOT/"staged/roster_2027_fast_ready.json").read_text())["players"]:
    currentBio[str(athlete[0])]=str(athlete[4] or "")
def heightInches(value):
    match=re.search(r"(\d+)'\s*(\d+)",str(value))
    return 12*int(match.group(1))+int(match.group(2)) if match else None
shots=defaultdict(Counter)
for shard in range(128):
    doc=json.loads((ROOT/"staged/portal_shots_2026"/f"shots_{shard:03d}.json").read_text())
    for pid,events in doc["players"].items():
        for event in events:
            zone=event[8]
            shots[pid][zone]+=1
            shots[pid]["total"]+=1
            if int(event[3])==3:shots[pid]["three"]+=1
# Positions are five inferred functional recruiting roles, not Torvik roles
# and NOT % time played in each position; site staff assignments are kept.
def infer_pos(row):
    p=str(row.get("position") or "").upper().strip()
    mn=n(row,"minutes") or 0
    ast30=div(n(row,"ast"),mn,30) or 0
    reb30=div(n(row,"reb"),mn,30) or 0
    if p in ("PG",):return "1"
    if p in ("SG",):return "2"
    if p in ("SF",):return "3"
    if p in ("PF",):return "4"
    if p in ("C","CENTER"):return "5"
    if "G" in p and "F" not in p:return "1" if ast30>=3.6 else "2"
    if "C" in p:return "5"
    # ESPN lists many centers as F. Use athlete bio height plus demonstrated
    # interior activity to separate 4/5 without a third-party role model.
    bio=currentBio.get(str(row.get("athlete_id") or ""))
    if bio and p=="F":
        h=heightInches(bio)
        if h is not None and h>=82 and reb30>=7:return "5"

    if "F" in p:return "4" if reb30>=6.8 else "3"
    return "1" if ast30>=3.8 else "4" if reb30>=7.5 else "2"
rows=[]
for row in season:
    pid=str(row.get("athlete_id") or "")
    if not pid.isdigit():continue
    gp=n(row,"gp") or 0;mins=n(row,"minutes") or 0
    tid=str(row.get("team_id") or "")
    tm=team.get(tid)
    tComplete=bool(tm and tm["gp"]>=8 and .94 <=tm["minutes"]/(200*tm["gp"])<=1.11)
    onShare=div(mins,tm["minutes"]/5) if tComplete else None
    twoA=n(row,"two_pa");threeA=n(row,"three_pa");fga=n(row,"fga");fta=n(row,"fta")
    fga=fga if fga is not None else (twoA or 0)+(threeA or 0)
    pts=n(row,"pts");ast=n(row,"ast");oreb=n(row,"oreb");dreb=n(row,"dreb")
    tov=n(row,"tov")
    poss=(fga or 0)+.475*(fta or 0)+(tov or 0)
    shot=shots.get(pid,Counter())
    shotOK=bool((fga or 0)>=25 and shot["total"]>=.95*(fga or 0) and shot["total"]<=1.05*(fga or 0))
    usage=div(poss,onShare*(tm["fga"]+.475*tm["fta"]+tm["tov"]) if onShare else None,100)
    astPct=div(ast,(tm["fgm"]-(n(row,"fgm") or 0))*onShare if onShare else None,100)
    reboundOpp=oppRebounds.get(tid)
    # Percentage of available team rebounds while the athlete was on court.
    orebPct=div(oreb,onShare*((tm["oreb"] or 0)+(reboundOpp["dreb"] or 0)) if onShare and reboundOpp else None,100)
    drebPct=div(dreb,onShare*((tm["dreb"] or 0)+(reboundOpp["oreb"] or 0)) if onShare and reboundOpp else None,100)
    metrics={
     "pts30":div(pts,mins,30),
     "efg":div((n(row,"fgm") or 0)+.5*(n(row,"three_pm") or 0),fga,100),
     "ts":div(pts,2*((fga or 0)+.44*(fta or 0)),100),
     "ftRate":div(fta,fga,100),
     "rim30":div(shot["Rim"],mins,30) if shotOK else None,
     "mid30":div(shot["Midrange"],mins,30) if shotOK else None,
     "three30":div(threeA,mins,30),
     "usage":usage,
     "ast30":div(ast,mins,30),"astPct":astPct,"astTov":div(ast,tov),
     "tovPct":div(tov,poss,100),
     "stl30":div(n(row,"stl"),mins,30),"blk30":div(n(row,"blk"),mins,30),
     "twoPct":div(n(row,"two_pm"),twoA,100),"threePct":div(n(row,"three_pm"),threeA,100),
     "ftPct":div(n(row,"ftm"),fta,100),"threeRate":div(threeA,fga,100),
     "two30":div(twoA,mins,30),"reb30":div(n(row,"reb"),mins,30),
     "oreb30":div(oreb,mins,30),"dreb30":div(dreb,mins,30),
     "orebPct":orebPct,"drebPct":drebPct,
     "stocks30":div((n(row,"stl") or 0)+(n(row,"blk") or 0),mins,30),
     "fta30":div(fta,mins,30),"fga30":div(fga,mins,30)}
    pos=infer_pos(row)
    arr=[str(row.get("player_name") or ""),str(row.get("team_name") or ""),pos,int(gp),round(mins,2),
         [finite(metrics[k]) for k in METRICS],
         *[n(row,k) for k in ("two_pm","two_pa","three_pm","three_pa","ftm","fta")]]
    rows.append((pid,arr,metrics))
peers={p:{m:[] for m in METRICS} for p in "12345"}
counts=dict.fromkeys("12345",0)
for pid,row,ms in rows:
    pos=row[2]
    if row[3]<8 or row[4]<200:continue
    counts[pos]+=1
    for k,v in ms.items():
        if v is None:continue
        if k in SHOOT_MIN:
            att=row[7] if k=="twoPct" else row[9] if k=="threePct" else row[11] if k=="ftPct" else ((row[7] or 0)+(row[9] or 0))
            if k=="ts":att+=(row[11] or 0)*.44
            if att<SHOOT_MIN[k]:continue
        peers[pos][k].append(round(v,4))
for p in peers:
    for m in peers[p]:peers[p][m].sort()
assert min(counts.values())>=50,counts
assert len(rows)>=4900,len(rows)
data={"schemaVersion":2,"season":2026,"seasonLabel":"2025-26",
      "source":"Full Division I ESPN season box scores + original ESPN PBP shot locations and opponent game boxes, athlete ID joins",
      "metricNames":METRICS,"qualification":{"minGames":8,"minMinutes":200,**SHOOT_MIN},
      "positionBasis":"Our estimated 1-5 positional peer group from ESPN roster position and production; not measured on-court position",
      "peerCounts":counts,"byESPNId":{pid:r for pid,r,_ in rows},
      "peers":peers,"hasFullNationalCoverage":True,
      "qa":{"athletes":len(rows),"boxGames":len(game_logs),"shotPlayers":len(shots),
            "teamsWithCompleteBoxSamples":sum(.94<=v["minutes"]/(200*v["gp"])<=1.11 for v in team.values() if v["gp"]>0)}}
raw=json.dumps(data,separators=(",",":"),ensure_ascii=False)
(OUT/"overview_2026.json").write_text(raw)
(OUT/"overview_2026.js").write_text("window.PORTAL_OVERVIEW_2026_NATIONAL="+raw+";\n")
print("RESULT",json.dumps({"athletes":len(rows),"counts":counts,"qa":data["qa"],"bytes":len(raw)}))
