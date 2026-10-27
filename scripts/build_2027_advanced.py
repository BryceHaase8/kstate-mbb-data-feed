#!/usr/bin/env python3
"""Daily ESPN 2026-27 shot/on-off/positions publisher; verified samples only.

Uses *only* the existing hoopR/ESPN play and ESPN player-box collections.
Every game/team/player is joined by ESPN ID. No Torvik player data. Missing
play-by-play, incomplete shot coordinates, uncertain playing-time segments,
or non-five-player intervals are omitted (never manufactured).

Run from repository root after scripts/collect_2027_advanced.R.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv, gzip, itertools, json, math, re
from pathlib import Path

SEASON=2027
MOD=128
SHOT_TYPES={'JumpShot','LayUpShot','DunkShot','TipShot','Shot'}
SHOT_FIELDS=['gameId','teamId','opponentId','shotValue','made','courtX','courtY','assistId','zone']
METRICS=['pts','fga','fgm','twoA','twoM','threeA','threeM','fta','ftm','oreb','dreb','tov','ast','stl','blk','pf',
         'rimA','rimM','paintA','paintM','midA','midM','cornerA','cornerM','aboveA','aboveM','deepA','deepM']

def ident(value):
    value=str(value or '').strip()
    return str(int(float(value))) if re.fullmatch(r'\d+(?:\.0+)?',value) else ''

def num(v,default=0):
    try:
        n=float(v)
        return n if math.isfinite(n) else default
    except (TypeError,ValueError):return default

def yes(x):return str(x).lower() in {'true','1','t','yes'}
def clock(x):
    x=str(x or '')
    if not re.fullmatch(r'\d{1,2}:\d{2}',x):return None
    m,s=map(int,x.split(':'))
    return m*60+s if s<60 else None

def source_rows(path):
    with gzip.open(path,'rt',encoding='utf-8',newline='') as f:return list(csv.DictReader(f))

def source_box(path):
    if not path.exists():return {}
    result=defaultdict(dict)
    for r in source_rows(path):
        gid,tid,pid=map(lambda k:ident(r.get(k)),('game_id','team_id','athlete_id'))
        if not gid or not tid or not pid:continue
        minutes=num(r.get('minutes'))
        if minutes<0 or minutes>70:continue
        result[(gid,tid)][pid]={'min':minutes,'started':yes(r.get('started')),
           'fga':max(0,num(r.get('fga'))),'position':str(r.get('position') or 'G')}
    return result

def shot_event(ev,team,other):
    if ev.get('type_text') not in SHOT_TYPES or ident(ev.get('team_id'))!=team:return None
    value=int(num(ev.get('score_value'),0))
    if value not in (2,3):return None
    x,y=num(ev.get('coordinate_x'),float('nan')),num(ev.get('coordinate_y'),float('nan'))
    if not math.isfinite(x) or not math.isfinite(y) or not (-47.5<=x<=47.5 and -25.5<=y<=25.5):return None
    cx=-y if x<0 else y;cy=47-abs(x)
    if not -25.5<=cx<=25.5 or not 0<=cy<=47.5:return None
    dist=math.hypot(abs(x)-41.75,y)
    if value==2:zone='Rim' if dist<5 else 'Short Paint' if dist<8 else 'Midrange'
    else:
        join=5.25+math.sqrt((22+1.75/12)**2-(21+7.875/12)**2)
        zone='Deep 3' if dist>=26 else 'Corner 3' if cy<=join+1.2 and abs(cx)>=20.6 else 'Above Break 3'
    made=int(yes(ev.get('scoring_play')))
    return [ident(ev.get('game_id')),team,other,value,made,round(cx,2),round(cy,2),
       ident(ev.get('athlete_id_2')) if made else None,zone]

def split_stats(ev,team,other):
    tid=ident(ev.get('team_id'))
    if tid not in (team,other):return None
    kind=str(ev.get('type_text') or '');side='off' if tid==team else 'def'
    if kind in SHOT_TYPES:
        v=int(num(ev.get('score_value')))
        if v not in (2,3):return None
        made=int(yes(ev.get('scoring_play')))
        delta={'fga':1,'fgm':made,'pts':made*v,
               ('two' if v==2 else 'three')+'A':1,
               ('two' if v==2 else 'three')+'M':made}
        if made and ident(ev.get('athlete_id_2')):delta['ast']=1
        shot=shot_event(ev,tid,other if tid==team else team)
        if shot:
            z={'Rim':'rim','Short Paint':'paint','Midrange':'mid','Corner 3':'corner',
               'Above Break 3':'above','Deep 3':'deep'}[shot[8]]
            delta[z+'A']=1;delta[z+'M']=made
        return side,delta
    if kind in ('MadeFreeThrow','MissedFreeThrow'):
        made=int(yes(ev.get('scoring_play'))) if kind=='MadeFreeThrow' else 0
        return side,{'fta':1,'ftm':made,'pts':made}
    if 'Turnover' in kind:return side,{'tov':1}
    if kind=='Offensive Rebound':return side,{'oreb':1}
    if kind in ('Defensive Rebound','Steal','Block Shot','PersonalFoul'):
        key={'Defensive Rebound':'dreb','Steal':'stl','Block Shot':'blk','PersonalFoul':'pf'}[kind]
        return ('def' if tid==team else 'off'),{key:1}
    return None

def player_states(events,meta,pid,team):
    """Verify individual active status against the *actual* ESPN box minutes.

    Unknown halftime status is inferred only if a first substitution/actor
    proof exists; otherwise reject if neither box-minute boundary resolves it.
    """
    periods=defaultdict(list)
    for i,ev in enumerate(events):
        p=int(num(ev.get('period_number')))
        if p<1 or p>10:return None,'period_invalid'
        periods[p].append(i)
    if not periods or sorted(periods)!=list(range(1,max(periods)+1)):
        return None,'missing_period'
    states=[False]*len(events);initial={};on=0.
    for period,indices in sorted(periods.items()):
        length=1200 if period<=2 else 300
        subs=[];touch=False
        for i in indices:
            e=events[i];kind=str(e.get('type_text') or '')
            if kind=='Substitution' and ident(e.get('team_id'))==team and ident(e.get('athlete_id_1'))==pid:
                desc=str(e.get('text') or '').lower()
                if 'subbing out' in desc:subs.append(True)
                elif 'subbing in' in desc:subs.append(False)
                else:return None,'unrecognized_sub'
            elif kind!='Substitution' and ident(e.get('team_id'))==team and ident(e.get('athlete_id_1'))==pid:
                touch=True
        if period==1:active=meta['started']
        elif subs:active=subs[0]
        elif touch:active=True
        elif meta['min']<=on+2:active=False
        elif meta['min']>=on+length/60-2:active=True
        else:return None,'ambiguous_period'
        initial[period]=active
        previous=length
        for i in indices:
            e=events[i];t=clock(e.get('clock_display_value'))
            if t is None or t<0 or t>length+1:return None,'bad_clock'
            if t>previous+2:return None,'nonmonotonic_clock'
            if active:on+=max(0,previous-t)/60
            previous=min(previous,t)
            if e.get('type_text')=='Substitution' and ident(e.get('team_id'))==team and ident(e.get('athlete_id_1'))==pid:
                new='subbing in' in str(e.get('text') or '').lower()
                if active==new:return None,'sub_conflict'
                active=new
            elif (e.get('type_text') not in ('Substitution','Jumpball') and
                  ident(e.get('team_id'))==team and ident(e.get('athlete_id_1'))==pid and not active):
                return None,'actor_off_court'
            states[i]=active
        if active:on+=max(0,previous)/60
    if abs(on-meta['min'])>2.1:return None,'minutes_disagree'
    return {'states':states,'onMin':on,'initial':initial},None

def position_scores(meta):
    """2026-27 assignment priors: ESPN position plus verified roster size.

    This remains an estimated lineup role, never a measured tracking position.
    """
    v=str(meta.get('position') or '').upper().replace('-','/')
    priors={'PG':[7,2,-3,-7,-9],'SG':[3,7,1,-4,-8],
      'SF':[-4,1,7,4,-3],'PF':[-7,-3,3,7,3],
      'C':[-9,-7,-3,3,8], 'F':[-5,-3,4,6,3],
      'G':[4,5,1,-4,-8]}
    a=priors.get(v,priors['F'] if v.startswith('F') else priors['G'])[:]
    height,weight=meta.get('height'),meta.get('weight')
    if height and weight:
        target_h=(75,78,80,82,84);target_w=(185,195,207,222,239)
        for ix in range(5):
            a[ix]-=1.55*((height-target_h[ix])/4)**2+.7*((weight-target_w[ix])/48)**2
    return a

def attach_roster_size(box,roster_path):
    """Optional exact ESPN-ID, one-time season roster context; never a player join by name."""
    if not roster_path or not roster_path.exists():return 0
    doc=json.loads(roster_path.read_text())
    if doc.get('rosterSeason')!=2027 or not isinstance(doc.get('players'),list):
        raise ValueError('Unrecognized 2027 ESPN-ID roster size source')
    size={}
    for player in doc['players']:
        if not isinstance(player,list) or len(player)<6:continue
        pid=ident(player[0])
        h=re.search(r"(\d+)'\s*(\d+)",str(player[4]))
        w=re.search(r'\d+',str(player[5]))
        if not pid or not h or not w:continue
        inches=int(h.group(1))*12+int(h.group(2));lbs=int(w.group())
        if 62<=inches<=93 and 120<=lbs<=390:size[pid]=(inches,lbs)
    found=0
    for (_,team),players in box.items():
        for pid,meta in players.items():
            if pid in size:
                meta['height'],meta['weight']=size[pid];found+=1
    return found

def assign_roles(lineup,meta):
    ids=tuple(sorted(lineup))
    if len(ids)!=5:return None
    weights=[position_scores(meta[pid]) for pid in ids]
    perm=max(itertools.permutations(range(5)),key=lambda v:sum(weights[i][v[i]] for i in range(5)))
    return {ids[k]:perm[k] for k in range(5)}

def build(box,pbp_dir,out,season_stats=None):
    games=defaultdict(dict)
    for (gid,team),players in box.items():games[gid][team]=players
    all_shots=defaultdict(list)
    all_onoff=defaultdict(lambda:{'on':{'off':defaultdict(float),'def':defaultdict(float),'minutes':0.},
          'off':{'off':defaultdict(float),'def':defaultdict(float),'minutes':0.},'games':0,'teamIds':set(),'verifiedBoxMinutes':0.})
    role=defaultdict(lambda:{'roles':[0.]*5,'verifiedMinutes':0.,'knownSizeMinutes':0.,'games':set()})
    qa=Counter(); failure=Counter();source_games=0;shot_games=0
    for file in sorted(pbp_dir.glob('*.csv.gz')):
        gid=file.name.split('.')[0]
        teams=games.get(gid,{})
        if len(teams)!=2:failure['not_two_DI_box_teams']+=1;continue
        events=source_rows(file)
        if len(events)<50 or len(events)>2000:failure['bad_pbp_event_count']+=1;continue
        events.sort(key=lambda e:(int(num(e.get('period_number'))),int(num(e.get('sequence_number')))))
        if any(ident(e.get('game_id'))!=gid for e in events):failure['mismatched_game_id']+=1;continue
        h=ident(events[0].get('home_team_id'));a=ident(events[0].get('away_team_id'))
        if h==a or set(teams)!={h,a}:failure['mismatched_DI_team_id']+=1;continue
        source_games+=1;qa['pbpEvents']+=len(events)
        # Shot chart independently qualifies each team-game; lineup quality
        # must NEVER affect valid ESPN shot coordinates.
        for team in (h,a):
            other=a if team==h else h
            box_fga=sum(p['fga'] for p in teams[team].values())
            field=[e for e in events if ident(e.get('team_id'))==team and e.get('type_text') in SHOT_TYPES and
              int(num(e.get('score_value')) or 0) in (2,3)]
            valid=[(ident(e.get('athlete_id_1')),shot_event(e,team,other)) for e in field]
            valid=[(pid,s) for pid,s in valid if pid in teams[team] and s is not None]
            if box_fga<5 or len(field)<box_fga*.75 or len(field)>box_fga*1.25 or len(valid)<box_fga*.75:
                failure['shot_box_or_location_coverage']+=1;continue
            for pid,shot in valid:all_shots[pid].append(shot)
            shot_games+=1;qa['mappedShots']+=len(valid)
        # ON/OFF: separate player individual substitution reconstruction + box audit.
        states_by_team={}
        for team in (h,a):
            good={}
            for pid,meta in teams[team].items():
                if meta['min']<=0:continue
                result,reason=player_states(events,meta,pid,team)
                if reason:failure['onoff_'+reason]+=1;continue
                good[pid]=result
            states_by_team[team]=good
            for pid,record in good.items():
                m=teams[team][pid];v=all_onoff[pid];v['games']+=1;v['teamIds'].add(team)
                v['verifiedBoxMinutes']+=m['min']
                duration=sum(20 if p<=2 else 5 for p in {int(num(e.get('period_number'))) for e in events})
                v['on']['minutes']+=record['onMin'];v['off']['minutes']+=duration-record['onMin']
                for i,e in enumerate(events):
                    entry=split_stats(e,team,a if team==h else h)
                    if entry:
                        side,delta=entry;dest=v['on' if record['states'][i] else 'off'][side]
                        for k,value in delta.items():dest[k]+=value
                qa['verifiedPlayerGames']+=1
        # Five-player role inference is *separately* restricted to confirmed
        # intervals; an unknown substitution should not poison other samples.
        byperiod=defaultdict(list)
        for i,e in enumerate(events):byperiod[int(num(e.get('period_number')))].append(i)
        for team in (h,a):
            good=states_by_team[team]
            for period,indices in byperiod.items():
                previous=1200 if period<=2 else 300
                for i in indices:
                    e=events[i];t=clock(e.get('clock_display_value'))
                    if t is None or t>previous:previous=t if t is not None else previous;continue
                    seconds=previous-t;previous=t
                    if seconds<=0 or seconds>300:continue
                    lineup=set()
                    for pid,rec in good.items():
                        active=rec['states'][i]
                        if e.get('type_text')=='Substitution' and ident(e.get('team_id'))==team and ident(e.get('athlete_id_1'))==pid:
                            active=not active
                        if active:lineup.add(pid)
                    if len(lineup)!=5:
                        qa['unverifiedFivePlayerIntervals']+=1;continue
                    assignments=assign_roles(lineup,teams[team])
                    for pid,pos in assignments.items():
                        role[pid]['roles'][pos]+=seconds/60
                        role[pid]['verifiedMinutes']+=seconds/60
                        if teams[team][pid].get('height') and teams[team][pid].get('weight'):
                            role[pid]['knownSizeMinutes']+=seconds/60
                        role[pid]['games'].add(gid)
                    qa['verifiedFivePlayerIntervals']+=1
    if not source_games:return {'published':False,'reason':'no eligible complete 2026-27 PBP games'}
    out=Path(out)
    shotdir=out/'portal_shots_2027';offdir=out/'portal_onoff_2027';posdir=out/'portal_positions_2027'
    for d in (shotdir,offdir,posdir):d.mkdir(parents=True,exist_ok=True)
    source='Per-game hoopR/ESPN live play-by-play joined to validated D-I ESPN player box by game/team/athlete ID'
    for i in range(MOD):
        shots={pid:rows for pid,rows in all_shots.items() if int(pid)%MOD==i}
        for data in shots.values():data.sort(key=lambda v:(v[0],v[5],v[6]))
        write(shotdir/f'shots_{i:03d}.json',{'schemaVersion':1,'season':SEASON,'modulo':MOD,'shard':i,
              'fields':SHOT_FIELDS,'players':shots})
        on={}
        for pid,v in all_onoff.items():
            if int(pid)%MOD!=i:continue
            on[pid]={'on':{'minutes':round(v['on']['minutes'],2),'off':rounded(v['on']['off']),
                            'def':rounded(v['on']['def'])},
                     'off':{'minutes':round(v['off']['minutes'],2),'off':rounded(v['off']['off']),
                            'def':rounded(v['off']['def'])},
                     'games':v['games'],'teamIds':sorted(v['teamIds']),
                     'verifiedBoxMinutes':round(v['verifiedBoxMinutes'],2)}
        write(offdir/f'onoff_{i:03d}.json',{'schemaVersion':1,'season':SEASON,'modulo':MOD,'shard':i,'players':on})
        positions={}
        for pid,v in role.items():
            if int(pid)%MOD!=i or v['verifiedMinutes']<10:continue
            total=num((season_stats or {}).get(pid),0)
            if not total:
                total=sum(meta['min'] for (gid,tid),people in box.items() for k,meta in people.items() if k==pid)
            verified=v['verifiedMinutes']
            if verified>total+min(12,.03*total):failure['positions_over_box']+=1;continue
            positions[pid]=[[round(x,3) for x in v['roles']],round(verified,2),round(total,2),len(v['games']),
               round(v['knownSizeMinutes']/verified,3)]
        write(posdir/f'positions_{i:03d}.json',{'schemaVersion':1,'season':SEASON,'modulo':MOD,'shard':i,'players':positions})
    shot_manifest={'schemaVersion':1,'season':SEASON,'seasonLabel':'2026–27','modulo':MOD,
       'available':bool(all_shots),'complete':False,'source':source,
       'metrics':{'gamesInSource':source_games,'eligibleShotTeamGames':shot_games,
                  'validMappedShots':sum(map(len,all_shots.values()))},
       'caution':'Partial season and per-team validated only; absence is not a missed shot.'}
    off_manifest={'schemaVersion':1,'season':SEASON,'modulo':MOD,'gamesVerified':source_games,
       'playersWithVerifiedGameSplits':len(all_onoff),'source':source,
       'method':'Individual ESPN substitution states audited versus official box minutes; not a causal impact estimate',
       'failures':dict(failure)}
    pos_manifest={'schemaVersion':1,'season':SEASON,'modulo':MOD,'playersWithRoleTime':sum(1 for v in role.values() if v['verifiedMinutes']>=10),
       'source':source,'method':'Estimated roles assigned only on intervals with five confirmed active players; size unavailable uses roster-position prior',
       'verifiedFivePlayerIntervals':qa['verifiedFivePlayerIntervals'],'warnings':'Roles are estimates, not player-tracking; missing intervals excluded'}
    write(shotdir/'manifest.json',shot_manifest);write(offdir/'manifest.json',off_manifest);write(posdir/'manifest.json',pos_manifest)
    return {'published':True,'sourceGames':source_games,'shots':shot_manifest['metrics']['validMappedShots'],
      'onoffPlayers':len(all_onoff),'positionIntervals':qa['verifiedFivePlayerIntervals'],
      'failures':dict(failure)}

def rounded(obj):return {k:round(v,2) for k,v in obj.items() if v}
def write(path,obj):
    path.write_text(json.dumps(obj,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')

def main():
    a=argparse.ArgumentParser()
    a.add_argument('--box',default='data/advanced_2027_player_box.csv.gz')
    a.add_argument('--pbp',default='data/advanced_2027_pbp/games')
    a.add_argument('--out',default='public')
    a.add_argument('--stats',default='data/current_player_season_stats.csv')
    a.add_argument('--roster',default='data/roster_2027_advanced.json')
    args=a.parse_args()
    b=source_box(Path(args.box))
    size_count=attach_roster_size(b,Path(args.roster))
    minutes={}
    if Path(args.stats).exists():
        with Path(args.stats).open(newline='',encoding='utf-8') as f:
            for row in csv.DictReader(f):
                if str(row.get('season'))=='2027':minutes[ident(row.get('athlete_id'))]=num(row.get('minutes'))
    result=build(b,Path(args.pbp),Path(args.out),minutes)
    result['boxPlayersWithRosterSize']=size_count
    print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
