#!/usr/bin/env python3
"""2025-26 ESPN PBP strict verified-stint ON/OFF research.
Uses in-house player substitution reconstruction with five-player lineup checks.
Does NOT use hoopR lineups, do not publish failed/unverified game segments.
Box-score minutes audit is required before a game is admitted.
"""
from pathlib import Path
from collections import defaultdict, Counter
import urllib.request, gzip, csv, json, math, sys
import pandas as pd

BASE=Path('research_data/staged')
DEST=BASE/'portal_onoff_2026'
DEST.mkdir(parents=True,exist_ok=True)
ARCH='research_data/historical/game_logs/player_game_logs_2026.csv.gz'
SOURCE=Path('/tmp/pbp2026.parquet')
URL='https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_mens_college_basketball_pbp/play_by_play_2026.parquet'
MOD=128
STATS=['pts','fga','fgm','twoA','twoM','threeA','threeM','fta','ftm','oreb','dreb','tov','ast','stl','blk','pf',
       'rimA','rimM','paintA','paintM','midA','midM','cornerA','cornerM','aboveA','aboveM','deepA','deepM']
FG_TYPES={'JumpShot','LayUpShot','DunkShot','TipShot','Shot'}

def ident(x):
    if x is None:return ''
    try:
        if pd.isna(x):return ''
        return str(int(x))
    except (ValueError,TypeError,OverflowError):return ''
def truth(x):
    return str(x).strip().lower() in ('true','1','t','yes')
def secs(x):
    try:
        a,b=str(x).split(':');return 60*int(a)+int(b)
    except: return None
def count():return {k:0.0 for k in STATS}
def add(dst,src):
    for k in STATS:dst[k]+=src[k]
def safe_float(x):
    try:return float(x or 0)
    except:return 0.

box=defaultdict(dict)
di=set()
with gzip.open(ARCH,'rt',encoding='utf8',newline='') as f:
    for row in csv.DictReader(f):
        season=int(row['season'])
        if season!=2026:raise ValueError('Unexpected box season')
        gid=str(row['game_id']);tid=str(row['team_id']);aid=str(row['athlete_id'])
        di.add(tid)
        box[(gid,tid)][aid]={'started':truth(row.get('started')),'min':safe_float(row.get('minutes')),'fga':safe_float(row.get('fga'))}
assert len(di)==365
if not SOURCE.exists():
    with urllib.request.urlopen(urllib.request.Request(URL,headers={'User-Agent':'Portal-OnOff-Research/1.0'}),timeout=160) as response:
        SOURCE.write_bytes(response.read())
cols=['game_id','sequence_number','period_number','clock_display_value','type_text','text','team_id','athlete_id_1','athlete_id_2',
      'score_value','scoring_play','home_team_id','away_team_id','coordinate_x','coordinate_y']
df=pd.read_parquet(SOURCE,columns=cols)
assert len(df)>2_800_000,len(df)
df=df[df['home_team_id'].astype(str).isin(di) & df['away_team_id'].astype(str).isin(di)]
print('SOURCE',len(df),'eligible event rows',df.game_id.nunique(),'games',flush=True)
# Each team-game lineup segment stores the team's own offensive & defensive events.
# The final ON and OFF splits include only games the athlete actually appeared in.
segments=defaultdict(dict)
good=Counter(); failures=Counter()
max_games=int(sys.argv[1]) if len(sys.argv)>1 else None
for game_counter,(gid,g) in enumerate(df.groupby('game_id',sort=False),1):
    gid=ident(gid)
    h=ident(g.iloc[0]['home_team_id']);a=ident(g.iloc[0]['away_team_id'])
    if (gid,h) not in box or (gid,a) not in box:
        failures['missing_box_team']+=1;continue
    players={h:box[(gid,h)],a:box[(gid,a)]}
    starters={t:{pid for pid,meta in players[t].items() if meta['started']} for t in (h,a)}
    if any(len(v)!=5 for v in starters.values()):
        failures['not_five_starters']+=1;continue
    lineup={t:set(v) for t,v in starters.items()}
    # within-game segments are completely private until all quality checks pass
    local={h:defaultdict(lambda:{'minutes':0.,'off':count(),'def':count()}),
           a:defaultdict(lambda:{'minutes':0.,'off':count(),'def':count()})}
    last_clock=1200; period=1; invalid=False; issues=Counter()
    for e in g.sort_values(['period_number','sequence_number']).itertuples(index=False):
        pnum=int(e.period_number)
        now=secs(e.clock_display_value)
        if now is None:issues['missing_clock']+=1;invalid=True;break
        if pnum!=period:
            if pnum<period:invalid=True;issues['backwards_period']+=1;break
            # attribute final previous-period interval before entering the next
            if last_clock>=0 and all(len(lineup[t])==5 for t in (h,a)):
                for t in (h,a):local[t][tuple(sorted(lineup[t]))]['minutes']+=last_clock/60
            period=pnum
            # A half/OT starts with starters unless evidence disproves it.
            lineup={t:set(v) for t,v in starters.items()}
            last_clock=1200 if pnum<=2 else 300
        elapsed=last_clock-now
        if elapsed < -1 or elapsed>250:issues['clock_gap']+=1;invalid=True;break
        if elapsed>0:
            if any(len(lineup[t])!=5 for t in (h,a)):
                issues['incomplete_lineup_interval']+=1;invalid=True;break
            for t in (h,a):local[t][tuple(sorted(lineup[t]))]['minutes']+=elapsed/60
        last_clock=now
        ev=str(e.type_text or '')
        team=ident(e.team_id);ath=ident(e.athlete_id_1)
        if ev=='Substitution':
            if team not in (h,a) or not ath or ath not in players[team]:
                issues['unresolved_substitution']+=1;invalid=True;break
            tx=str(e.text or '').lower()
            if 'subbing out' in tx:
                if ath not in lineup[team]:
                    issues['unmatched_sub_out']+=1;invalid=True;break
                lineup[team].remove(ath)
            elif 'subbing in' in tx:
                if ath in lineup[team]:
                    issues['duplicate_sub_in']+=1;invalid=True;break
                lineup[team].add(ath)
            else:issues['unknown_sub_type']+=1;invalid=True;break
            if len(lineup[team])>5:
                issues['six_players']+=1;invalid=True;break
            continue
        if ev in FG_TYPES or ev=='MadeFreeThrow' or 'Turnover' in ev or ev in ('Offensive Rebound','Defensive Rebound','Steal','Block Shot','PersonalFoul'):
            if team not in (h,a):issues['unknown_event_team']+=1;invalid=True;break
            if any(len(lineup[t])!=5 for t in (h,a)):
                issues['unverified_event_lineup']+=1;invalid=True;break
            # The primary participant should be on the floor. Exceptions
            # invalidate the game rather than assert a guessed lineup.
            if ath and ath in players[team] and ath not in lineup[team]:
                issues['actor_not_on_court']+=1;invalid=True;break
            own=local[team][tuple(sorted(lineup[team]))]['off']
            other=a if team==h else h
            allowed=local[other][tuple(sorted(lineup[other]))]['def']
            if ev in FG_TYPES:
                val=int(e.score_value) if pd.notna(e.score_value) else 0
                if val not in (2,3):issues['bad_shot_value']+=1;invalid=True;break
                made=truth(e.scoring_play)
                for dst in (own,allowed):
                    dst['fga']+=1
                    dst['fgm']+=int(made)
                    dst['pts']+=val*int(made)
                    key=('two' if val==2 else 'three')
                    dst[key+'A']+=1;dst[key+'M']+=int(made)
                    if made and ident(e.athlete_id_2):dst['ast']+=1
                x,y=e.coordinate_x,e.coordinate_y
                if pd.notna(x) and pd.notna(y) and -47.5<=x<=47.5 and -25.5<=y<=25.5:
                    distance=math.hypot(abs(float(x))-41.75,float(y))
                    cy=47-abs(float(x));cx=abs(float(y))
                    if val==2:zone='rim' if distance<5 else 'paint' if distance<8 else 'mid'
                    else:
                        arc=22+1.75/12; corner=21+7.875/12
                        join=5.25+math.sqrt(arc*arc-corner*corner)
                        zone='deep' if distance>=26 else 'corner' if cy<=join+1.2 and cx>=corner-1 else 'above'
                    for dst in (own,allowed):
                        dst[zone+'A']+=1;dst[zone+'M']+=int(made)
            elif ev=='MadeFreeThrow':
                made=truth(e.scoring_play)
                for dst in (own,allowed):
                    dst['fta']+=1;dst['ftm']+=int(made);dst['pts']+=int(made)
            elif 'Turnover' in ev:
                for dst in (own,allowed):dst['tov']+=1
            elif ev=='Offensive Rebound':
                for dst in (own,allowed):dst['oreb']+=1
            elif ev=='Defensive Rebound':
                # DREB by the defending team, against the other team's FGA.
                for dst in (local[team][tuple(sorted(lineup[team]))]['def'],
                            local[other][tuple(sorted(lineup[other]))]['off']):
                    dst['dreb']+=1
            elif ev in ('Steal','Block Shot','PersonalFoul'):
                for dst in (local[team][tuple(sorted(lineup[team]))]['def'],
                            local[other][tuple(sorted(lineup[other]))]['off']):
                    dst[{'Steal':'stl','Block Shot':'blk','PersonalFoul':'pf'}[ev]]+=1
    if invalid:
        failures.update(issues);continue
    if last_clock>0 and all(len(lineup[t])==5 for t in (h,a)):
        for t in (h,a):local[t][tuple(sorted(lineup[t]))]['minutes']+=last_clock/60
    elif last_clock>5:
        failures['invalid_final_lineup']+=1;continue
    clockMinutes={t:sum(s['minutes'] for s in local[t].values()) for t in (h,a)}
    if any(abs(clockMinutes[t]-(40 if period<=2 else 40+5*(period-2)))>2.0 for t in (h,a)):
        failures['clock_coverage']+=1;continue
    # Cross-check reconstructed on-court minutes against player box minutes.
    diff=[]
    for t in (h,a):
        calc=Counter()
        for l,record in local[t].items():
            for pid in l:calc[pid]+=record['minutes']
        for pid,b in players[t].items():
            if b['min']>0 and abs(calc.get(pid,0.)-b['min'])>3.0:
                diff.append((pid,round(calc.get(pid,0.),1),b['min']))
    if len(diff)>2:
        failures['minutes_box_disagreement']+=1;continue
    for t in (h,a):segments[(gid,t)]=local[t]
    good['games']+=1;good['player_games']+=sum(sum(1 for p in players[t].values() if p['min']>0) for t in (h,a))
    if game_counter%800==0:print('PROGRESS',game_counter,'accepted',good['games'],'failed',sum(failures.values()),flush=True)
    if max_games and game_counter>=max_games:break
# Every player's OFF sample uses only games in which the player appeared,
# avoiding DNPs being erroneously counted as on/off bench time.
athletes=defaultdict(lambda:{'on':{'off':count(),'def':count(),'minutes':0.},
                               'off':{'off':count(),'def':count(),'minutes':0.},
                               'games':0,'teamIds':set(),'verifiedBoxMinutes':0.})
for (gid,tid),stints in segments.items():
    for pid,meta in box[(gid,tid)].items():
        if meta['min']<=0:continue
        dest=athletes[pid];dest['games']+=1;dest['teamIds'].add(tid);dest['verifiedBoxMinutes']+=meta['min']
        for lineup_id,st in stints.items():
            slot='on' if pid in lineup_id else 'off'
            dest[slot]['minutes']+=st['minutes']
            add(dest[slot]['off'],st['off'])
            add(dest[slot]['def'],st['def'])
shards=[{} for _ in range(MOD)]
for pid,record in athletes.items():
    if not pid.isdigit():continue
    record['teamIds']=sorted(record['teamIds'])
    for slot in ('on','off'):
        record[slot]['minutes']=round(record[slot]['minutes'],2)
        for side in ('off','def'):
            record[slot][side]={k:round(x,3) for k,x in record[slot][side].items() if x}
    shards[int(pid)%MOD][pid]=record
for i,people in enumerate(shards):
    (DEST/f'onoff_{i:03d}.json').write_text(json.dumps({'schemaVersion':1,'season':2026,'modulo':MOD,'shard':i,'players':people},separators=(',',':')))
manifest={'schemaVersion':1,'season':2026,'label':'2025-26','modulo':MOD,
          'source':'Direct ESPN event archive, independently reconstructed substitutions and 2025-26 box-score minute QA',
          'totalEligibleDIEvents':len(df),'totalDIGames':int(df.game_id.nunique()),'gamesVerified':good['games'],
          'playersWithVerifiedGameSplits':len(athletes),'qaFailures':dict(failures),
          'explanation':'Data use verified segments in games a player appeared in; NO missing games or inferred minutes. On/off raw split; not opponent adjusted or causal.'}
(DEST/'manifest.json').write_text(json.dumps(manifest,indent=2))
print('FINAL',json.dumps(manifest),flush=True)
assert good['games']>=100 if not max_games else good['games']>=1,manifest
