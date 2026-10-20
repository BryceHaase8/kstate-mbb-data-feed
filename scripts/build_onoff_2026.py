#!/usr/bin/env python3
"""Research-only 2025-26 PBP On/Off.
Substitution-state reconstructed PER PLAYER, from verified game starters and the
first 2H substitution direction; checked against official game minutes and
player's own on-court actions. Never infer every 5-man lineup from missing subs.
OFF = only bench possessions in games the athlete appeared. No DNP dates.
Exclude overtime and unverified player-games. Descriptive, not causal / RAPM.
"""
import sys,json,gzip,csv,urllib.request,math,collections
from pathlib import Path
import pandas as pd
root=Path("research_data/staged"); out=root/"portal_onoff_2026";out.mkdir(parents=True,exist_ok=True)
pbpfile=Path("/tmp/onoff_pbp_2026.parquet")
if not pbpfile.exists():
 url="https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_mens_college_basketball_pbp/play_by_play_2026.parquet"
 with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"Portal-OnOff-QA/1.0"}),timeout=150) as r:pbpfile.write_bytes(r.read())
assert pbpfile.stat().st_size>80000000
COLS=["game_id","period_number","end_period_seconds_remaining","sequence_number","type_text","text","team_id","athlete_id_1","athlete_id_2","scoring_play","score_value","coordinate_x","coordinate_y","points_attempted"]
KCOL={k:i for i,k in enumerate(COLS)}
d=pd.read_parquet(pbpfile,columns=COLS)
assert len(d)>2500000
def sid(v):
 if v is None or pd.isna(v):return ""
 try:return str(int(v))
 except (ValueError,TypeError):return ""
def num(v):
 if v is None or pd.isna(v):return 0.
 try:return float(v)
 except (ValueError,TypeError):return 0.
def yes(v):return str(v).lower() in ("true","t","1","yes")
box=collections.defaultdict(dict);games=collections.defaultdict(set)
with gzip.open("research_data/historical/game_logs/player_game_logs_2026.csv.gz","rt",encoding="utf8") as f:
 for r in csv.DictReader(f):
  g,t,p=r["game_id"],r["team_id"],r["athlete_id"]
  if not g or not t or not p:continue
  box[(g,t)][p]={"started":yes(r.get("started")),"minutes":num(r.get("minutes")),"fga":num(r.get("fga"))}
  games[g].add(t)
eligible={g for g,ts in games.items() if len(ts)==2 and all(sum(x["started"] for x in box[(g,t)].values())==5 for t in ts)}
d=d[d.game_id.notna() & d.game_id.isin(set(map(int,eligible)))]
d=d.sort_values(["game_id","period_number","end_period_seconds_remaining","sequence_number"],ascending=[True,True,False,True],kind="stable")
KEYS=["pts","fga","fgm","twoa","twom","threea","threem","fta","ftm","oreb","dreb","tov","ast","stl","blk","pf","rim_a","rim_m","paint_a","paint_m","mid_a","mid_m","corner_a","corner_m","atb_a","atb_m","deep_a","deep_m"]
I={k:i for i,k in enumerate(KEYS)};N=len(KEYS);SHOT={"JumpShot","LayUpShot","DunkShot","TipShot","Shot"}
def zero():return [0.]*N
def add(x,y):
 for i,v in enumerate(y):x[i]+=v
def stats(row):
 typ=str(row[KCOL["type_text"]] or "")
 if typ not in SHOT and typ not in ("MadeFreeThrow","Offensive Rebound","Defensive Rebound","Steal","Block Shot","PersonalFoul") and "Turnover" not in typ:return None
 x=zero();made=yes(row[KCOL["scoring_play"]])
 if typ in SHOT:
  val=int(num(row[KCOL["points_attempted"]])) or int(num(row[KCOL["score_value"]]))
  if val not in (2,3):return None
  x[I["fga"]]=1;x[I["fgm"]]=int(made);x[I["pts"]]=val if made else 0
  if val==2:x[I["twoa"]]=1;x[I["twom"]]=int(made)
  else:x[I["threea"]]=1;x[I["threem"]]=int(made)
  if made and sid(row[KCOL["athlete_id_2"]]):x[I["ast"]]=1
  rx=num(row[KCOL["coordinate_x"]]);ry=num(row[KCOL["coordinate_y"]])
  if -47.5<=rx<=47.5 and -25.5<=ry<=25.5:
   dis=math.hypot(abs(rx)-41.75,ry);courtY=47-abs(rx)
   if val==2:zone="rim" if dis<5 else "paint" if dis<8 else "mid"
   else:
    join=5.25+math.sqrt((22+1.75/12)**2-(21+7.875/12)**2)
    zone="deep" if dis>=26 else "corner" if courtY<=join+1.2 and abs(ry)>=21+7.875/12-1 else "atb"
   x[I[zone+"_a"]]=1;x[I[zone+"_m"]]=int(made)
 elif typ=="MadeFreeThrow":x[I["fta"]]=1;x[I["ftm"]]=int(made);x[I["pts"]]=int(made)
 elif typ=="Offensive Rebound":x[I["oreb"]]=1
 elif typ=="Defensive Rebound":x[I["dreb"]]=1
 elif "Turnover" in typ:x[I["tov"]]=1
 elif typ=="Steal":x[I["stl"]]=1
 elif typ=="Block Shot":x[I["blk"]]=1
 elif typ=="PersonalFoul":x[I["pf"]]=1
 return x
combined=collections.defaultdict(lambda:{"onO":zero(),"offO":zero(),"onD":zero(),"offD":zero(),"games":0,"onMinutes":0.,"offMinutes":0.})
coverage=collections.Counter();failures=collections.Counter();goodgames=set()
available=collections.Counter()
for (g,t),people in box.items():
 for pid,entry in people.items():
  if entry["minutes"]>0:available[(pid,t)]+=1
def process(g,raw):
 teams=sorted(games[g]);t0,t1=teams
 entries={t:box[(g,t)] for t in teams}
 events=[];shotCounts=collections.Counter();periods=set()
 for row in raw:
  per=int(num(row[KCOL["period_number"]]));periods.add(per)
  if per not in (1,2):return "overtime"
  clock=max(0.,min(1200.,num(row[KCOL["end_period_seconds_remaining"]])))
  tid=sid(row[KCOL["team_id"]]);actor=sid(row[KCOL["athlete_id_1"]])
  typ=str(row[KCOL["type_text"]] or ""); desc=str(row[KCOL["text"]] or "").lower()
  sc=stats(row) if tid in teams else None
  if sc is not None and tid in teams:shotCounts[tid]+=sc[I["fga"]]
  events.append((per,clock,tid,actor,typ,desc,sc))
 if len(periods)<2:return "missing_half"
 for t in teams:
  if abs(shotCounts[t]-sum(x["fga"] for x in entries[t].values()))>3:return "game_fga_mismatch"
 passed=0
 for t in teams:
  opp=t1 if t==t0 else t0
  for pid,info in entries[t].items():
   if info["minutes"]<=0:continue
   # 2H initial state is derived from first substitution action for that player.
   # With no subs: direct participation in 2H implies on throughout; otherwise
   # treat as off. The independent box-minute validation is the final gate.
   first2=next((ev for ev in events if ev[0]==2 and ev[2]==t and ev[3]==pid and ev[4]=="Substitution"),None)
   if first2:
    state2="subbing out" in first2[5]
    if "subbing out" not in first2[5] and "subbing in" not in first2[5]:failures["ambiguous_second_half"]+=1;continue
   else:
    state2=any(ev[0]==2 and ev[2]==t and ev[3]==pid and ev[6] is not None for ev in events)
   on=info["started"];period=1;last=1200.;mins=0.
   current={"onO":zero(),"offO":zero(),"onD":zero(),"offD":zero()}
   ok=True
   for per,clock,tid,actor,typ,desc,sc in events:
    if per!=period:
     if on:mins+=last/60.
     period=per;last=1200.;on=state2
    diff=last-clock
    if diff < -0.5:ok=False;break
    if on and diff>0:mins+=diff/60.
    last=clock
    if typ=="Substitution" and tid==t and actor==pid:
     if "subbing out" in desc:
      if not on:ok=False;break
      on=False
     elif "subbing in" in desc:
      if on:ok=False;break
      on=True
    if sc is None:continue
    # A player's recorded shot/rebound/TO/steal/block/foul is evidence of being on.
    if tid==t and actor==pid and (typ in SHOT or typ in ("Offensive Rebound","Defensive Rebound","Steal","Block Shot") or "Turnover" in typ):
     if not on:ok=False;break
    side="O" if tid==t else "D" if tid==opp else None
    if side is not None:add(current[("on" if on else "off")+side],sc)
   if on:mins+=last/60.
   if not ok:failures["substitution_or_activity_conflict"]+=1;continue
   if abs(mins-info["minutes"])>2.5:failures["minute_mismatch"]+=1;continue
   if mins<0 or mins>41:failures["invalid_minutes"]+=1;continue
   target=combined[(pid,t)]
   for key in ("onO","offO","onD","offD"):add(target[key],current[key])
   target["games"]+=1
   target["onMinutes"]+=mins;target["offMinutes"]+=max(0,40-mins)
   passed+=1
 if passed:goodgames.add(g)
 coverage["gamesWithValidPlayers"]+=int(passed>0)
 coverage["playerGamesValidated"]+=passed
 return "used" if passed else "no_valid_player_states"
limit=int(sys.argv[1]) if len(sys.argv)>1 else 0
for game,grp in d.groupby("game_id",sort=False):
 g=str(int(game))
 outcome=process(g,grp[COLS].itertuples(index=False,name=None))
 coverage[outcome]+=1
 if limit and coverage["used"]+coverage["no_valid_player_states"]+sum(coverage[k] for k in ("overtime","missing_half","game_fga_mismatch"))>=limit:break
print("QA",json.dumps({"processedGames":sum(coverage[k] for k in ("used","no_valid_player_states","overtime","missing_half","game_fga_mismatch")),"counts":dict(coverage),"playerFailures":dict(failures),"playerIDs":len(combined)},indent=2))
if limit:sys.exit(0)
people=[{} for _ in range(128)]
for (pid,team),row in combined.items():
 dct={"teamId":team,"games":row["games"],"gamesAvailable":available[(pid,team)],
      "onMinutes":round(row["onMinutes"],1),"offMinutes":round(row["offMinutes"],1)}
 for key in ("onO","offO","onD","offD"):dct[key]=[round(x,3) for x in row[key]]
 people[int(pid)%128].setdefault(pid,[]).append(dct)
n=sum(len(sh) for sh in people)
assert len(goodgames)>=2000 and n>=2500,(len(goodgames),n,dict(coverage))
manifest={"schemaVersion":1,"season":2026,"seasonLabel":"2025-26","modulo":128,
"fields":KEYS,"validatedGames":len(goodgames),"attemptedGames":sum(coverage[k] for k in ("used","no_valid_player_states","overtime","missing_half","game_fga_mismatch")),
"validatedPlayerGames":coverage["playerGamesValidated"],"excluded":dict(failures),"players":n,
"source":"ESPN national 2025-26 PBP + archived game box-score starters and minutes",
"method":"Individual player ON/OFF substitution-state reconstruction; 2H inferred from first sub; independent game FGA, athlete action and minute checks. OFF bench-only in appeared games.",
"notOpponentAdjusted":True,"notCausal":True}
(out/"manifest.json").write_text(json.dumps(manifest,indent=2))
for i,roster in enumerate(people):
 (out/f"onoff_{i:03d}.json").write_text(json.dumps({"schemaVersion":1,"season":2026,"modulo":128,"shard":i,"fields":KEYS,"players":roster},separators=(",",":")))
print("RESULT",json.dumps({"validatedGames":len(goodgames),"playerIDs":n,"playerGames":coverage["playerGamesValidated"]},indent=2))
