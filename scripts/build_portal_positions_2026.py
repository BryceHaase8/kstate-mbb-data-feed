#!/usr/bin/env python3
"""2025-26 Positions: minutes by inferred 1..5 roles in verified five-player ESPN intervals.
Cannot substitute unverified full lineups or raw player ON/OFF for five-man stints.
Derived from ESPN substitution timeline, player box minutes, size and production.
"""
from collections import defaultdict,Counter
from pathlib import Path
from itertools import permutations
import pandas as pd
import gzip,csv,json,math,urllib.request,sys,re

SOURCE=Path('/tmp/pbp2026.parquet')
URL='https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_mens_college_basketball_pbp/play_by_play_2026.parquet'
BASE=Path('research_data')
DEST=BASE/'staged/portal_positions_2026'
DEST.mkdir(exist_ok=True,parents=True)
BOX=BASE/'historical/game_logs/player_game_logs_2026.csv.gz'
MOD=128
def ident(x):
    try:
        if pd.isna(x):return ''
        return str(int(x))
    except (ValueError,TypeError,OverflowError):return ''
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

box=defaultdict(dict)
di=set()
with gzip.open(BOX,'rt',encoding='utf8',newline='') as f:
    for row in csv.DictReader(f):
        gid,tid,pid=(str(row[x]) for x in ('game_id','team_id','athlete_id'))
        di.add(tid)
        box[(gid,tid)][pid]={'started':truth(row.get('started')),'min':numeric(row.get('minutes'))}
assert len(di)==365
profiles={}
with gzip.open(BASE/'historical/season_totals/player_season_2026.csv.gz','rt',encoding='utf8') as f:
    for r in csv.DictReader(f):
        pid=str(r.get('athlete_id') or '')
        if not pid:continue
        minutes=numeric(r.get('minutes'))
        def per30(field):return numeric(r.get(field))*30/minutes if minutes>0 else 0.
        profiles[pid]={'position':str(r.get('position') or '').upper(),
           'ast30':per30('ast'),'reb30':per30('reb'),'blk30':per30('blk'),
           'three30':per30('three_pa'), 'oreb30':per30('oreb'),
           'height':None,'weight':None,'knownSize':False}
roster=json.loads((BASE/'staged/roster_2027_fast_ready.json').read_text())['players']
for athlete in roster:
    pid=str(athlete[0])
    if pid not in profiles:continue
    profile=profiles[pid]
    hm=re.search(r"(\d+)'\\s*(\d+)",str(athlete[4]))
    wm=re.search(r"(\d+)",str(athlete[5]))
    profile['height']=int(hm.group(1))*12+int(hm.group(2)) if hm else None
    profile['weight']=int(wm.group(1)) if wm else None
    profile['knownSize']=profile['height'] is not None and profile['weight'] is not None

TARGET_HEIGHT=[75,78,80,82,84]
TARGET_WEIGHT=[185,195,207,222,239]
def role_score(pid,pos):
    p=profiles.get(pid,{})
    listed=p.get('position','')
    h=p.get('height')
    w=p.get('weight')
    if h is None:h=76 if listed.startswith('G') else 83 if 'C' in listed else 80
    if w is None:w=185 if listed.startswith('G') else 245 if 'C' in listed else 214
    ix=pos-1
    score=-1.55*((h-TARGET_HEIGHT[ix])/4.0)**2-0.7*((w-TARGET_WEIGHT[ix])/48.0)**2
    ast=p.get('ast30',0);reb=p.get('reb30',0);blk=p.get('blk30',0);three=p.get('three30',0);oreb=p.get('oreb30',0)
    score += [0.62*ast+0.11*three-0.11*reb,
              0.18*ast+0.29*three-0.055*reb,
              0.12*ast+0.20*three+0.09*reb,
              0.16*reb+0.15*oreb+0.17*blk-0.045*ast,
              0.25*reb+0.22*oreb+0.31*blk-0.16*three][ix]
    if listed in ('PG','G'):
        if pos in (1,2):score+=.95
    elif listed in ('F','PF','SF'):
        if pos in (3,4):score+=.8
    elif listed in ('C','CENTER'):
        if pos==5:score+=1.5
    return score

lineup_cache={}
def assign_positions(lineup):
    lineup=tuple(sorted(lineup))
    if lineup in lineup_cache:return lineup_cache[lineup]
    if len(lineup)!=5:return None
    candidate=max(permutations(range(1,6)),key=lambda xs:sum(role_score(pid,position) for pid,position in zip(lineup,xs)))
    result=tuple(zip(lineup,candidate))
    lineup_cache[lineup]=result
    return result

if not SOURCE.exists():
    with urllib.request.urlopen(urllib.request.Request(URL,headers={'User-Agent':'Portal-Positions-Research/1.0'}),timeout=180) as r:
        SOURCE.write_bytes(r.read())
cols=['game_id','period_number','clock_display_value','sequence_number','type_text','text','team_id',
      'athlete_id_1','home_team_id','away_team_id']
df=pd.read_parquet(SOURCE,columns=cols)
df=df[df.home_team_id.astype(str).isin(di)&df.away_team_id.astype(str).isin(di)]
groups=df.groupby('game_id',sort=False)
LIMIT=int(sys.argv[1]) if len(sys.argv)>1 else None
print('SOURCE',len(df),'PBP events',len(groups),'D-I games',flush=True)
assigned=defaultdict(lambda:{'roles':[0.]*5,'verifiedMinutes':0.,'gameSet':set(),'knownSizeMinutes':0.})
stats=Counter()
qa=Counter()
team_game_coverage=Counter()
for game_idx,(game,g) in enumerate(groups,1):
    gid=ident(game)
    home=ident(g.iloc[0]['home_team_id']);away=ident(g.iloc[0]['away_team_id'])
    if (gid,home) not in box or (gid,away) not in box:
        qa['missing_team_box']+=1;continue
    g=g.assign(_clock_sort=g['clock_display_value'].map(clock))
    g=g.sort_values(['period_number','_clock_sort','sequence_number'],
                    ascending=[True,False,True],kind='stable')
    events=g.to_dict('records')
    periods=defaultdict(list)
    for i,e in enumerate(events):
        p=int(e['period_number'])
        periods[p].append(i)
    validated={}
    for team in (home,away):
        result={}
        for pid,meta in box[(gid,team)].items():
            if meta['min']<=0:continue
            state,error=player_segments(events,periods,meta,pid,team)
            if error:qa[error]+=1;continue
            result[pid]=state
        validated[team]=result
    # For each true clock interval assign roles only if precisely five
    # box-minute-verified athletes on this team are identified.
    # At each substitution timestamp, pre-event lineup comes from state
    # after the preceding event. At period boundary, first pre-event
    # state is inferred from the first event's post-state and sub direction.
    for p,indices in periods.items():
        length=1200 if p<=2 else 300
        before=length
        previous=None
        for idx in indices:
            event=events[idx]
            now=clock(event['clock_display_value'])
            if now is None or now<0 or now>length+1 or now>before+2:
                qa['bad_time_interval']+=1;break
            elapsed=max(0,before-now)/60.
            if elapsed>=1/60:
                for team in (home,away):
                    valid=validated[team]
                    if previous is None:
                        lineup=[]
                        for pid,state in valid.items():
                            after=state['states'][idx]
                            is_sub=event['type_text']=='Substitution' and ident(event['team_id'])==team and ident(event['athlete_id_1'])==pid
                            was_on=not after if is_sub else after
                            if was_on:lineup.append(pid)
                    else:
                        lineup=[pid for pid,state in valid.items() if state['states'][previous]]
                    if len(lineup)!=5:
                        qa['not_exactly_five']+=1;continue
                    assignment=assign_positions(lineup)
                    for pid,pos in assignment:
                        player=assigned[pid]
                        player['roles'][pos-1]+=elapsed
                        player['verifiedMinutes']+=elapsed
                        player['gameSet'].add(gid)
                        if profiles.get(pid,{}).get('knownSize'):
                            player['knownSizeMinutes']+=elapsed
                    team_game_coverage[(gid,team)]+=elapsed
                    stats['verifiedLineupIntervals']+=1
                    stats['verifiedTeamMinutes']+=elapsed
            before=now
            previous=idx
        if previous is not None and before>=1:
            elapsed=before/60
            for team in (home,away):
                valid=validated[team]
                lineup=[pid for pid,state in valid.items() if state['states'][previous]]
                if len(lineup)!=5:continue
                for pid,pos in assign_positions(lineup):
                    player=assigned[pid];player['roles'][pos-1]+=elapsed
                    player['verifiedMinutes']+=elapsed;player['gameSet'].add(gid)
                    if profiles.get(pid,{}).get('knownSize'):player['knownSizeMinutes']+=elapsed
                team_game_coverage[(gid,team)]+=elapsed
                stats['verifiedLineupIntervals']+=1
                stats['verifiedTeamMinutes']+=elapsed
    if game_idx%800==0:print('PROGRESS',game_idx,dict(stats),'uniquePlayers',len(assigned),flush=True)
    if LIMIT and game_idx>=LIMIT:break
# Box denominator counts all real player appearances, not only verified games.
season_minutes={}
with gzip.open(BASE/'historical/season_totals/player_season_2026.csv.gz','rt',encoding='utf8') as f:
    for row in csv.DictReader(f):
        season_minutes[str(row['athlete_id'])]=numeric(row.get('minutes'))
shards=[{} for _ in range(MOD)]
qa['playersOverBox'] = 0
for pid,value in assigned.items():
    observed=value['verifiedMinutes']
    total=season_minutes.get(pid,0)
    # Exclude impossible total minutes even if some intervals were individually plausible.
    if total<=0 or observed>total+min(12,0.03*total):
        qa['playersOverBox']+=1;continue
    if observed<10:continue
    roles=[round(v,3) for v in value['roles']]
    assert abs(sum(roles)-observed)<.05,(pid,roles,observed)
    shards[int(pid)%MOD][pid]=[roles,round(observed,2),round(total,2),len(value['gameSet']),
                              round(value['knownSizeMinutes']/observed,3)]
for i,people in enumerate(shards):
    (DEST/f'positions_{i:03d}.json').write_text(json.dumps({
      'schemaVersion':1,'season':2026,'shard':i,'modulo':MOD,'players':people},
      separators=(',',':')))
manifest={'schemaVersion':1,'season':2026,'seasonLabel':'2025-26',
    'modulo':MOD,'gamesInSource':len(groups),
    'gamesWithVerifiedLineups':len({g for g,t in team_game_coverage}),
    'teamsGamesVerified':len(team_game_coverage),
    'verifiedTeamMinutes':round(stats['verifiedTeamMinutes'],1),
    'verifiedLineupIntervals':stats['verifiedLineupIntervals'],
    'playersWithRoleTime':sum(len(s) for s in shards),
    'source':'ESPN archived PBP substitution order and 2025-26 box minutes; ESPN season stats; ESPN roster height/weight where available',
    'method':'Assign exactly one 1/2/3/4/5 to each box-verified five-player stint using size/production; not measured tracking positions',
    'qa':dict(qa),'minimumDisplayMinutes':10,
    'warnings':'Some lineups/periods unverified. Coverage is assigned role minutes divided by full ESPN player season minutes; role shares are shares of verified lineup time only.'}
(DEST/'manifest.json').write_text(json.dumps(manifest,indent=2))
print('FINAL',json.dumps(manifest),flush=True)
if LIMIT:
    assert stats['verifiedLineupIntervals']>=LIMIT//2,manifest
else:
    assert stats['verifiedLineupIntervals']>5000,manifest
