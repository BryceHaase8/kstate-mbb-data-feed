#!/usr/bin/env python3
"""Research-only PBP-driven 2025-26 player ON/OFF, using independently validated
5-man lineups, archived ESPN starters/box score, substitution timelines, and
per-game minute / FGA checks. No proprietary roster/staff data, no model fitting.
Only verified two-half, D-I vs D-I games contribute. OFF means bench possessions
in games the player appeared, never team games the player did not play.
"""
import sys,json,gzip,csv,urllib.request,math,collections
from pathlib import Path
import pandas as pd
root=Path("research_data/staged")
out=root/"portal_onoff_2026"
out.mkdir(parents=True,exist_ok=True)
pbp_file=Path("/tmp/onoff_pbp_2026.parquet")
if not pbp_file.exists():
    url="https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_mens_college_basketball_pbp/play_by_play_2026.parquet"
    with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"Portal-OnOff-QA/1.0"}),timeout=150) as r:
        pbp_file.write_bytes(r.read())
assert pbp_file.stat().st_size>80000000
COLS=["game_id","period_number","end_period_seconds_remaining","sequence_number","type_text","text","team_id","athlete_id_1","athlete_id_2","scoring_play","score_value","coordinate_x","coordinate_y","points_attempted"]
d=pd.read_parquet(pbp_file,columns=COLS)
C={k:i for i,k in enumerate(COLS)}
assert len(d)>2500000
d=d[d.game_id.notna() & d.team_id.notna() | (d.type_text.astype(str).isin(["Jumpball","End Period","End Game","Substitution"]))]
# Game keys and teams are exact ESPN IDs, never fuzzy names.
def sid(v):
    if v is None or pd.isna(v):return ""
    try:return str(int(v))
    except (ValueError,TypeError):return ""
def num(v):
    if v is None or pd.isna(v):return 0.
    try:return float(v)
    except (ValueError,TypeError):return 0.
def yes(v):return str(v).strip().lower() in ("true","t","1","yes")
box=collections.defaultdict(dict);games=collections.defaultdict(set)
with gzip.open("research_data/historical/game_logs/player_game_logs_2026.csv.gz","rt",encoding="utf8") as f:
    for r in csv.DictReader(f):
        game,team,pid=r["game_id"],r["team_id"],r["athlete_id"]
        if not game or not team or not pid:continue
        box[(game,team)][pid]={"start":yes(r.get("started")),"mins":num(r.get("minutes")),"fga":num(r.get("fga")),"pts":num(r.get("points"))}
        games[game].add(team)
valid_games={g for g,teams in games.items() if len(teams)==2 and all(sum(x["start"] for x in box[(g,t)].values())==5 for t in teams)}
d=d[d.game_id.isin(set(map(int,valid_games)))]
d=d.sort_values(["game_id","period_number","end_period_seconds_remaining","sequence_number"],ascending=[True,True,False,True],kind="stable")
KEYS=["pts","fga","fgm","twoa","twom","threea","threem","fta","ftm","oreb","dreb","tov","ast","stl","blk","pf","rim_a","rim_m","paint_a","paint_m","mid_a","mid_m","corner_a","corner_m","atb_a","atb_m","deep_a","deep_m"]
K={k:i for i,k in enumerate(KEYS)};N=len(KEYS)
def blank():return [0.]*N
def add(a,b):
    for i,v in enumerate(b):a[i]+=v
SHOT={"JumpShot","LayUpShot","DunkShot","TipShot","Shot"}
def event_stats(row):
    typ=str(row[C["type_text"]] or "")
    if typ not in SHOT and typ not in ("MadeFreeThrow","Offensive Rebound","Defensive Rebound","Steal","Block Shot","PersonalFoul") and "Turnover" not in typ:return None
    x=blank();made=yes(row[C["scoring_play"]])
    if typ in SHOT:
        val=int(num(row[C["points_attempted"]])) or int(num(row[C["score_value"]]))
        if val not in (2,3):return None
        x[K["fga"]]=1
        x[K["pts"]]=val if made else 0
        x[K["fgm"]]=int(made)
        if val==2:x[K["twoa"]]=1;x[K["twom"]]=int(made)
        else:x[K["threea"]]=1;x[K["threem"]]=int(made)
        if made and sid(row[C["athlete_id_2"]]):x[K["ast"]]=1
        rawx=num(row[C["coordinate_x"]]);rawy=num(row[C["coordinate_y"]])
        if -47.5<=rawx<=47.5 and -25.5<=rawy<=25.5:
            dist=math.hypot(abs(rawx)-41.75,rawy)
            cy=47-abs(rawx);cx=abs(rawy)
            if val==2:zone="rim" if dist<5 else "paint" if dist<8 else "mid"
            else:
                join=5.25+math.sqrt((22+1.75/12)**2-(21+7.875/12)**2)
                zone="deep" if dist>=26 else "corner" if cy<=join+1.2 and cx>=21+7.875/12-1 else "atb"
            x[K[zone+"_a"]]=1;x[K[zone+"_m"]]=int(made)
    elif typ=="MadeFreeThrow":x[K["fta"]]=1;x[K["ftm"]]=int(made);x[K["pts"]]=int(made)
    elif typ=="Offensive Rebound":x[K["oreb"]]=1
    elif typ=="Defensive Rebound":x[K["dreb"]]=1
    elif "Turnover" in typ:x[K["tov"]]=1
    elif typ=="Steal":x[K["stl"]]=1
    elif typ=="Block Shot":x[K["blk"]]=1
    elif typ=="PersonalFoul":x[K["pf"]]=1
    return x

def decode_period_clock(row):
    period=int(num(row[C["period_number"]]))
    time=num(row[C["end_period_seconds_remaining"]])
    return period,max(0,min(1200,time))

aggregated=collections.defaultdict(lambda:{"onO":blank(),"offO":blank(),"onD":blank(),"offD":blank(),"playedGames":set(),"onMinutes":0.,"offMinutes":0.})
game_count=0
quali=collections.Counter()
game_skips=collections.Counter()
examples=[]
limit=int(sys.argv[1]) if len(sys.argv)>1 else 0

def run_game(g, group):
    global game_count
    teams=sorted(games[g]);t0,t1=teams
    roster={t:box[(g,t)] for t in teams}
    starting={t:{pid for pid,p in roster[t].items() if p["start"]} for t in teams}
    if any(len(v)!=5 for v in starting.values()):return "bad_starters"
    lineups={t:set(starting[t]) for t in teams}
    minutes={t:collections.defaultdict(float) for t in teams}
    shadow=collections.defaultdict(lambda:{"onO":blank(),"offO":blank(),"onD":blank(),"offD":blank()})
    state={t:blank() for t in teams}
    count={t:blank() for t in teams}
    last=1200.
    current_period=1
    dirty=False
    saw_event=False
    def flush():
        nonlocal state
        if not any(any(x) for x in state.values()):return
        for t in teams:
            other=t1 if t==t0 else t0
            if len(lineups[t])!=5 or len(lineups[other])!=5:raise ValueError("invalid_five")
            for pid,p in roster[t].items():
                if p["mins"]<=0 and pid not in starting[t]:continue
                cell=shadow[(t,pid)]
                tag="on" if pid in lineups[t] else "off"
                add(cell[tag+"O"],state[t]);add(cell[tag+"D"],state[other])
        state={t:blank() for t in teams}
    def elapse(clock):
        nonlocal last
        elapsed=last-clock
        if elapsed < -1 or elapsed>1200:raise ValueError("clock_order")
        if elapsed>0:
            for t in teams:
                for pid in lineups[t]:minutes[t][pid]+=elapsed/60
        last=clock
    prev_sub_clock=None
    in_sub=False
    try:
        for row in group:
            period,clock=decode_period_clock(row)
            if period>2:return "overtime"
            if period!=current_period:
                if period!=current_period+1:return "period_gap"
                flush();elapse(0)
                # The second-half five are provisional. Independently reject
                # games whose reconstructed minutes fail the box-score audit.
                lineups={t:set(starting[t]) for t in teams}
                state={t:blank() for t in teams}
                current_period=period;last=1200;in_sub=False;prev_sub_clock=None
            typ=str(row[C["type_text"]] or "")
            if in_sub and (typ!="Substitution" or clock!=prev_sub_clock):
                if any(len(lineups[t])!=5 for t in teams):return "unbalanced_sub_group"
                in_sub=False
            elapse(clock)
            team=sid(row[C["team_id"]])
            if typ=="Substitution":
                if team not in teams:continue
                pid=sid(row[C["athlete_id_1"]]);t=str(row[C["text"]] or "").lower()
                if not pid or pid not in roster[team]:return "unknown_sub_player"
                if not in_sub:
                    flush();in_sub=True;prev_sub_clock=clock
                if "subbing out" in t:
                    if pid not in lineups[team]:return "sub_out_not_on"
                    lineups[team].remove(pid)
                elif "subbing in" in t:
                    if pid in lineups[team]:return "sub_in_already_on"
                    lineups[team].add(pid)
                else:return "unrecognized_substitution"
                continue
            if team not in teams:continue
            st=event_stats(row)
            if st is not None:
                if len(lineups[t0])!=5 or len(lineups[t1])!=5:return "not_five_at_event"
                add(state[team],st)
                add(count[team],st)
                saw_event=True
        if in_sub and any(len(lineups[t])!=5 for t in teams):return "unbalanced_final_sub"
        flush();elapse(0)
    except ValueError as e:return str(e)
    if not saw_event:return "no_events"
    # Require independently consistent reconstructed minutes and field-goal
    # counts. Otherwise exclude the entire game, never patch unknown players.
    for t in teams:
        if abs(count[t][K["fga"]]-sum(x["fga"] for x in roster[t].values()))>3:return "fga_mismatch"
        missed=[]
        for pid,stat in roster[t].items():
            model=minutes[t].get(pid,0)
            if stat["mins"]<=0 and model<1:continue
            missed.append(abs(model-stat["mins"]))
        if missed and (sum(missed)>24 or max(missed)>8):return "minute_mismatch"
    for t in teams:
        for pid,p in roster[t].items():
            if p["mins"]<=0 and pid not in starting[t]:continue
            key=(pid,t);cell=shadow[(t,pid)];target=aggregated[key]
            for k in ("onO","offO","onD","offD"):add(target[k],cell[k])
            target["playedGames"].add(g)
            target["onMinutes"]+=minutes[t].get(pid,0.)
            target["offMinutes"]+=max(0,40-minutes[t].get(pid,0.))
    return "PASS"

gp_available=collections.Counter()
for (g,t),roster in box.items():
    for pid,p in roster.items():
        if p["mins"]>0:gp_available[(pid,t)]+=1
for game,grp in d.groupby("game_id",sort=False):
    g=str(int(game))
    try:outcome=run_game(g,grp[COLS].itertuples(index=False,name=None))
    except Exception as e:
        raise RuntimeError(f"failure for {g}: {e}")
    quali[outcome]+=1
    if outcome=="PASS":game_count+=1
    elif len(examples)<35:examples.append([g,outcome])
    if limit and sum(quali.values())>=limit:break
print("RUN",json.dumps({"processed":sum(quali.values()),"passed":game_count,"statuses":dict(quali),"sampleFailures":examples},indent=2))
if limit:sys.exit(0)
# Keep result isolated in research branch; output means and classifications are
# descriptive, NOT RAPM, opponent-adjusted impact, or causal estimates.
players=[{} for _ in range(128)]
for (pid,team),row in aggregated.items():
    obj={"teamId":team,"games":len(row["playedGames"]),"gamesAvailable":gp_available[(pid,team)],
         "onMinutes":round(row["onMinutes"],1),"offMinutes":round(row["offMinutes"],1)}
    for key in ("onO","offO","onD","offD"):obj[key]=[round(x,3) for x in row[key]]
    players[int(pid)%128].setdefault(pid,[]).append(obj)
n=sum(len(players[i]) for i in range(128))
assert game_count>=2000 and n>=2400,(game_count,n,dict(quali))
manifest={"schemaVersion":1,"season":2026,"seasonLabel":"2025-26","modulo":128,
"fields":KEYS,"teams":365,"validatedGames":game_count,"attemptedGames":sum(quali.values()),
"excluded":{k:v for k,v in quali.items() if k!="PASS"},"players":n,
"source":"ESPN 2025-26 national play by play + archived box starters",
"method":"5-on-5 substitution-state reconstruction; minute and FGA QA per game; full-game exclusion upon mismatch; OFF uses bench possessions in games appeared",
"notAdjusted":True}
(out/"manifest.json").write_text(json.dumps(manifest,indent=2))
for i,people in enumerate(players):
    (out/f"onoff_{i:03d}.json").write_text(json.dumps({"schemaVersion":1,"season":2026,"modulo":128,"shard":i,"fields":KEYS,"players":people},separators=(",",":")))
print("RESULT",json.dumps({"validatedGames":game_count,"players":n,"skips":dict(quali)},indent=2))
