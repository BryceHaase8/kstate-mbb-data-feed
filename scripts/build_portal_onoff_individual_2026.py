#!/usr/bin/env python3
"""Research: player-level ESPN on/off from substitution & box-minute auditing.
No hoopR-derived lineup. No claims about complete five-player lineups or RAPM.
D-I vs D-I events only; only player-games passing on-court minute verification.
"""
from collections import defaultdict,Counter
from pathlib import Path
import pandas as pd
import gzip,csv,json,math,urllib.request,sys

DATA=Path('research_data/staged/portal_onoff_2026')
DATA.mkdir(exist_ok=True,parents=True)
SOURCE=Path('/tmp/pbp2026.parquet')
URL='https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_mens_college_basketball_pbp/play_by_play_2026.parquet'
BOX='research_data/historical/game_logs/player_game_logs_2026.csv.gz'
MOD=128
FG={'JumpShot','LayUpShot','DunkShot','TipShot','Shot'}
METRICS=['pts','fga','fgm','twoA','twoM','threeA','threeM','fta','ftm','oreb','dreb','tov','ast','stl','blk','pf',
         'rimA','rimM','paintA','paintM','midA','midM','cornerA','cornerM','aboveA','aboveM','deepA','deepM']
def ident(x):
    try:
        if pd.isna(x):return ''
        return str(int(x))
    except (TypeError,ValueError,OverflowError):return ''
def numeric(x):
    try:
        if pd.isna(x):return 0.
        return float(x)
    except (ValueError,TypeError):return 0.
def truth(x):return str(x).lower() in ('true','1','t','yes')
def clock(x):
    try:
        a,b=str(x).split(':')
        return int(a)*60+int(b)
    except (ValueError,AttributeError):return None
def blank():return defaultdict(float)
def add(dst,src):
    for k,v in src.items():dst[k]+=v

box=defaultdict(dict);di=set()
with gzip.open(BOX,'rt',encoding='utf8',newline='') as f:
    for row in csv.DictReader(f):
        gid=str(row['game_id']);team=str(row['team_id']);pid=str(row['athlete_id'])
        box[(gid,team)][pid]={'started':truth(row.get('started')),'min':numeric(row.get('minutes'))}
        di.add(team)
assert len(di)==365
if not SOURCE.exists():
    with urllib.request.urlopen(urllib.request.Request(URL,headers={'User-Agent':'Portal-OnOff-QA/1.0'}),timeout=160) as d:
        SOURCE.write_bytes(d.read())
columns=['game_id','period_number','clock_display_value','sequence_number','type_text','text','team_id',
         'athlete_id_1','athlete_id_2','scoring_play','score_value','home_team_id','away_team_id','coordinate_x','coordinate_y']
df=pd.read_parquet(SOURCE,columns=columns)
df=df[df.home_team_id.astype(str).isin(di)&df.away_team_id.astype(str).isin(di)]
groups=df.groupby('game_id',sort=False)
print('SOURCE',len(df),'events',len(groups),'games',flush=True)
nation=defaultdict(lambda:{'on':{'off':blank(),'def':blank(),'minutes':0.},'off':{'off':blank(),'def':blank(),'minutes':0.},
                           'games':0,'teamIds':set(),'verifiedBoxMinutes':0.})
qa=Counter();qa_detail=Counter()
LIMIT=int(sys.argv[1]) if len(sys.argv)>1 else None
# Event classification is independent of athlete on/off; apply each team event
# to its own offense/defense and opponent's opposing side.
def describe(ev,team,other):
    typ=str(ev['type_text'] or '')
    team_id=ident(ev['team_id'])
    if team_id not in (team,other):return None
    actor_side='off' if team_id==team else 'def'
    if typ in FG:
        value=int(numeric(ev['score_value']))
        if value not in (2,3):return None
        made=truth(ev['scoring_play'])
        delta={'fga':1,'fgm':int(made),'pts':value*int(made)}
        prefix='two' if value==2 else 'three'
        delta[prefix+'A']=1;delta[prefix+'M']=int(made)
        if made and ident(ev['athlete_id_2']):delta['ast']=1
        x,y=ev['coordinate_x'],ev['coordinate_y']
        if pd.notna(x) and pd.notna(y) and -47.5<=x<=47.5 and -25.5<=y<=25.5:
            x,y=float(x),float(y)
            distance=math.hypot(abs(x)-41.75,y)
            if value==2:z='rim' if distance<5 else 'paint' if distance<8 else 'mid'
            else:
                radius=22+1.75/12;corner=21+7.875/12
                join=5.25+math.sqrt(radius*radius-corner*corner)
                zy=47-abs(x)
                z='deep' if distance>=26 else 'corner' if zy<=join+1.2 and abs(y)>=corner-1 else 'above'
            delta[z+'A']=1;delta[z+'M']=int(made)
        return actor_side,delta
    if typ=='MadeFreeThrow':
        made=truth(ev['scoring_play'])
        return actor_side,{'fta':1,'ftm':int(made),'pts':int(made)}
    if 'Turnover' in typ:return actor_side,{'tov':1}
    if typ=='Offensive Rebound':return actor_side,{'oreb':1}
    # These three events describe DEFENSIVE actions by the event team.
    if typ in ('Defensive Rebound','Steal','Block Shot','PersonalFoul'):
        side='def' if team_id==team else 'off'
        return side,{{'Defensive Rebound':'dreb','Steal':'stl','Block Shot':'blk','PersonalFoul':'pf'}[typ]:1}
    return None
def player_segments(events,periods,meta,pid,team):
    """Build reliable player states across periods, excluding ambiguous halves.
    A known initial state is derived from starters for period 1 and the
    first substitution or player events in subsequent periods.
    """
    total=0.; states={}; reasons=[]
    min_box=meta['min']
    for number,indices in periods.items():
        period_length=1200 if number<=2 else 300
        subs=[]
        touches=False
        for i in indices:
            e=events[i]
            if e['type_text']=='Substitution' and ident(e['team_id'])==team and ident(e['athlete_id_1'])==pid:
                tx=str(e['text'] or '').lower()
                if 'subbing out' in tx:subs.append((i,True))
                elif 'subbing in' in tx:subs.append((i,False))
                else:return None,'unknown_sub'
            if e['type_text']!='Substitution' and ident(e['team_id'])==team and ident(e['athlete_id_1'])==pid:
                touches=True
        if number==1:state=bool(meta['started'])
        elif subs:state=subs[0][1]
        elif touches:state=True
        elif min_box<=total+2:state=False
        elif min_box>=total+period_length/60-2:state=True
        else:return None,'ambiguous_period'
        prior=period_length
        for i in indices:
            e=events[i]
            at=clock(e['clock_display_value'])
            if at is None or at<0 or at>period_length+1:return None,'bad_clock'
            if at>prior+2:return None,'nonmonotonic_clock'
            elapsed=max(0,prior-at)
            if state:total+=elapsed/60
            prior=min(prior,at)
            if e['type_text']=='Substitution' and ident(e['team_id'])==team and ident(e['athlete_id_1'])==pid:
                tx=str(e['text'] or '').lower()
                new='subbing in' in tx
                if state==new:return None,'sub_state_conflict'
                state=new
            else:
                # Primary athlete proof of being on floor at a recorded
                # offensive or defensive event for the athlete's team.
                if ident(e['team_id'])==team and ident(e['athlete_id_1'])==pid and e['type_text'] not in ('Jumpball',):
                    if not state:return None,'actor_off_court'
            states[i]=state
        if state:total+=max(0,prior)/60
    if abs(total-min_box)>2.1:return None,'minutes_disagreement'
    if len(states)!=len(events):return None,'missing_period'
    return {'states':states,'onMin':total},''
for ix,(gid,g) in enumerate(groups,1):
    gid=ident(gid)
    home=ident(g.iloc[0]['home_team_id']);away=ident(g.iloc[0]['away_team_id'])
    if (gid,home) not in box or (gid,away) not in box:qa['missing_box']+=1;continue
    # ESPN's global sequence_number may not be chronological within a game.
    # Order by period and descending displayed clock first; use sequence only
    # for events sharing an identical timestamp (including substitutions).
    g=g.assign(_clock_sort=g['clock_display_value'].map(clock))
    g=g.sort_values(['period_number','_clock_sort','sequence_number'],ascending=[True,False,True],kind='stable')
    events=g.to_dict('records')
    periods=defaultdict(list)
    for i,e in enumerate(events):periods[int(e['period_number'])].append(i)
    # Build per-player event classifications once per game, then attribute by
    # validated individual states. No guessing of full lineups.
    per_team={}
    for team,other in ((home,away),(away,home)):
        per_team[team]=[describe(e,team,other) for e in events]
    good_this=0
    for team in (home,away):
        for pid,meta in box[(gid,team)].items():
            if meta['min']<=0:continue
            state,error=player_segments(events,periods,meta,pid,team)
            if error:
                qa_detail[error]+=1
                continue
            player=nation[pid];player['games']+=1;player['teamIds'].add(team);player['verifiedBoxMinutes']+=meta['min']
            good_this+=1
            for i,e in enumerate(events):
                entry=per_team[team][i]
                if entry:
                    side,values=entry
                    grp='on' if state['states'][i] else 'off'
                    add(player[grp][side],values)
            player['on']['minutes']+=state['onMin']
            player['off']['minutes']+=sum((1200 if x<=2 else 300) for x in periods)/60-state['onMin']
    if good_this:qa['gamesWithVerifiedPlayers']+=1;qa['verifiedPlayerGames']+=good_this
    if ix%750==0:print('PROGRESS',ix,'with verified',qa['gamesWithVerifiedPlayers'],'player-games',qa['verifiedPlayerGames'],'failures',qa_detail.most_common(4),flush=True)
    if LIMIT and ix>=LIMIT:break
out=[{} for _ in range(MOD)]
for pid,v in nation.items():
    if not pid.isdigit():continue
    v['teamIds']=sorted(v['teamIds'])
    v['verifiedBoxMinutes']=round(v['verifiedBoxMinutes'],2)
    for flag in ('on','off'):
        v[flag]['minutes']=round(v[flag]['minutes'],2)
        for side in ('off','def'):
            v[flag][side]={k:round(a,2) for k,a in v[flag][side].items() if a}
    out[int(pid)%MOD][pid]=v
for i,p in enumerate(out):
    (DATA/f'onoff_{i:03d}.json').write_text(json.dumps({'schemaVersion':1,'season':2026,'shard':i,'modulo':MOD,'players':p},separators=(',',':')))
manifest={'schemaVersion':1,'season':2026,'label':'2025-26','modulo':MOD,
 'source':'Public ESPN 2025-26 PBP, substitution-inferred per-player stints audited vs ESPN box minutes',
 'method':'Independent player-state ON/OFF, NOT full five-player lineup reconstruction; no RAPM adjustment',
 'events':len(df),'gamesInSource':int(len(groups)),'gamesVerified':qa['gamesWithVerifiedPlayers'],
 'verifiedPlayerGames':qa['verifiedPlayerGames'],'playersWithVerifiedGameSplits':len(nation),
 'failedPlayerGameReasons':dict(qa_detail),'availability':'Only games for which individual minutes pass QA',
 'limitation':'Sample coverage differs by player; descriptive, not causal or schedule-adjusted'}
(DATA/'manifest.json').write_text(json.dumps(manifest,indent=2))
print('FINAL',json.dumps(manifest),flush=True)
if LIMIT:
    assert qa['verifiedPlayerGames']>=LIMIT//2,manifest
else:
    assert qa['verifiedPlayerGames']>=20_000,manifest
