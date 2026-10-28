#!/usr/bin/env python3
"""2026-27 ESPN shot, independent player On/Off, and estimated five-player roles.

Only data with full game-level box/clock/identity validation becomes publishable.
A valid game is cached immutably so later missing ESPN data cannot delete it.
Every absent/unverifiable game is explicitly excluded (never imputed).
Production must NEVER synthesize current-season stats or mix historic 2025-26 data.
"""
from __future__ import annotations
import collections,csv,gzip,json,math,pathlib,re,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
MOD=128
SEASON=2027
STAT_KEYS=('pts','fga','fgm','twoA','twoM','threeA','threeM','fta','ftm','oreb','dreb','tov','ast','stl','blk','pf')
SHOT_FIELDS=['gameId','teamId','opponentId','shotValue','made','courtX','courtY','assistId','zone']
RIM=5.25
def integer(v):
 try:return int(float(v))
 except (TypeError,ValueError,OverflowError):return None
def number(v):
 try:
  x=float(v)
  return x if math.isfinite(x) else None
 except (TypeError,ValueError):return None
def parse_seconds(s):
 m=re.fullmatch(r'\s*(\d{1,2}):(\d{2})(?:\.(\d+))?\s*',str(s or ''))
 if not m or int(m.group(2))>=60:return None
 return int(m.group(1))*60+int(m.group(2))+float('0.'+m.group(3)) if m.group(3) else int(m.group(1))*60+int(m.group(2))
def read_csv(path):
 with gzip.open(path,'rt',encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def save_json(path,data):
 path.parent.mkdir(parents=True,exist_ok=True)
 temp=path.with_name(path.name+'.tmp')
 temp.write_text(json.dumps(data,separators=(',',':'),ensure_ascii=False)+'\n',encoding='utf-8')
 temp.replace(path)
def zero():return {k:0 for k in STAT_KEYS}
def kind(row):
 typ=str(row.get('type_text') or '').lower()
 txt=str(row.get('text') or '').lower()
 if 'free throw' in typ or 'free throw' in txt:return 'ft'
 if 'substitution' in typ or 'substitution' in txt or re.search(r'\bsub (?:in|out)\b',typ):return 'sub'
 if ('shot' in typ or 'jumper' in typ or 'layup' in typ or 'dunk' in typ or 'tip-in' in typ or 'hook' in typ or
     re.search(r'\b(?:makes|made|misses|missed)\b',txt)) and re.search(r'\b(?:makes?|made|miss(?:es|ed)?)\b',txt):
  return 'shot'
 if 'offensive rebound' in typ or 'offensive rebound' in txt:return 'oreb'
 if 'defensive rebound' in typ or 'defensive rebound' in txt:return 'dreb'
 if 'turnover' in typ or 'turnover' in txt:return 'tov'
 if 'steal' in typ:return 'stl'
 if 'block shot' in typ or 'blocked shot' in typ:return 'blk'
 if 'foul' in typ or 'foul' in txt:return 'pf'
 return None
def make_status(row):
 txt=str(row.get('text') or '').lower()
 return bool(re.search(r'\b(?:makes?|made)\b',txt)) and not bool(re.search(r'\bmiss(?:es|ed)?\b',txt))
def shot_three(row):
 text=(str(row.get('text') or '')+' '+str(row.get('type_text') or '')).lower()
 return bool(re.search(r'(?:\b3\s*[- ]\s*(?:pt|point|pointer)|\bthree\s*[- ]?\s*(?:pt|point|pointer))',text)) or (make_status(row) and integer(row.get('score_value'))==3)
def zone_for(x,y,three):
 d=math.hypot(x,y-RIM)
 if three:
  if abs(x)>=21.5 and y<19:return 'Corner 3'
  return 'Deep 3' if d>=27 else 'Above Break 3'
 return 'Rim' if d<5 else 'Short Paint' if d<9 else 'Midrange'
def court_candidate(x,y,mode):
 # hoopR's normalized full-game PBP has historically supplied a 94x50
 # centered lengthwise frame (hoop at |x|~41.75). A separate ESPN
 # half-court representation uses x=0..50, y in feet toward center.
 # Never guess: score both conventions against shot distances in ESPN text.
 if mode=='lengthwise':
  if not -47.5<=x<=47.5 or not -25.5<=y<=25.5:return None
  cx=(-y if x<0 else y)
  cy=47-abs(x)
 elif mode=='halfcourt':
  if not 0<=x<=50 or not -1<=y<=42:return None
  cx=x-25;cy=y+RIM
 else:return None
 if not -25<=cx<=25 or not 0<=cy<=47:return None
 return round(cx,2),round(cy,2)
def coordinate_frame(events):
 labelled=[]
 for ev in events:
  if kind(ev)!='shot':continue
  text=str(ev.get('text') or '').lower()
  m=re.search(r'\b(\d{1,2})\s*[- ]\s*foot\b',text)
  target=float(m.group(1)) if m else 2.5 if any(z in text for z in ('layup','dunk','tip-in','putback')) else None
  if target is None:continue
  x=number(ev.get('coordinate_x'));y=number(ev.get('coordinate_y'))
  if x is None or y is None:continue
  labelled.append((x,y,target))
 if not labelled:return None
 losses={}
 for mode in ('lengthwise','halfcourt'):
  errors=[]
  for x,y,d in labelled:
   p=court_candidate(x,y,mode)
   if p is not None:errors.append(abs(math.hypot(p[0],p[1]-RIM)-d))
  if len(errors)>=max(1,math.ceil(.8*len(labelled))):
   errors.sort()
   losses[mode]=errors[len(errors)//2]
 if not losses:return None
 best=min(losses,key=losses.get)
 if losses[best]>6:return None
 if len(losses)==2 and losses[best]+2>losses[next(k for k in losses if k!=best)]:
  return None # coordinate convention unresolved, don't plot fake zones
 return best
def load_box(path):
 teams=collections.defaultdict(dict)
 for row in read_csv(path):
  team=str(row.get('team_id') or '')
  pid=str(row.get('athlete_id') or '')
  gid=str(row.get('game_id') or '')
  mins=number(row.get('minutes'))
  if not(team.isdigit() and pid.isdigit() and gid.isdigit()) or mins is None or mins<0:continue
  teams[gid][pid]={**row,'team':team,'minutes':mins,
                   'started':integer(row.get('started'))==1,
                   'fga':integer(row.get('fga')),'fgm':integer(row.get('fgm')),
                   'three_pa':integer(row.get('three_pa')),
                   'three_pm':integer(row.get('three_pm')),
                   'team_score':integer(row.get('team_score'))}
 return teams
def shot_game(gid,events,box):
 teams={r['team'] for r in box.values()}
 if len(teams)!=2:return None,'not_two_teams'
 teammates={t:set(pid for pid,r in box.items() if r['team']==t) for t in teams}
 counts=collections.defaultdict(lambda:[0,0,0,0])
 out=collections.defaultdict(list)
 frame=coordinate_frame(events)
 if frame is None:return None,'shot_coordinate_frame_unverified'
 for ev in events:
  if kind(ev)!='shot':continue
  team=str(ev.get('team_id') or '')
  pid=str(ev.get('athlete_id_1') or '')
  if team not in teams or pid not in teammates[team]:return None,'shot_identity'
  made=make_status(ev);three=shot_three(ev)
  rawx=number(ev.get('coordinate_x'));rawy=number(ev.get('coordinate_y'))
  coord=court_candidate(rawx,rawy,frame) if rawx is not None and rawy is not None else None
  if coord is None:return None,'shot_coordinates_missing_or_changed'
  x,y=coord
  made_i=int(made);three_i=int(three)
  counts[pid][0]+=1;counts[pid][1]+=made_i
  counts[pid][2]+=three_i;counts[pid][3]+=made_i*three_i
  other=next(iter(teams-{team}))
  aid=str(ev.get('athlete_id_2') or '')
  out[pid].append([gid,team,other,3 if three else 2,made_i,x,y,aid if aid.isdigit() and aid!=pid else None,zone_for(x,y,three)])
 for pid,r in box.items():
  # Refuse partial/mismatched shooting plays. Do not claim complete season
  # coverage based on the shot events available in the PBP.
  target=(r['fga'],r['fgm'],r['three_pa'],r['three_pm'])
  if any(x is None for x in target):return None,'box_shooting_missing'
  if tuple(counts[pid])!=target:return None,'shot_box_disagreement'
 return dict(out),None
def elapsed(row):
 p=integer(row.get('period_number'));remaining=parse_seconds(row.get('clock_display_value'))
 if p is None or p<1 or p>9 or remaining is None:return None
 length=1200 if p<=2 else 300
 if not -1e-8<=remaining<=length+1e-8:return None
 return (p-1)*1200 if p<=2 else 2400+(p-3)*300, length-remaining
def role_sort(pid,box,roster):
 row=box[pid]
 rp=roster.get(pid) or []
 pos=str(row.get('position') or (rp[3] if len(rp)>3 else '') or '').upper()
 bases={'PG':0,'SG':1,'SF':2,'PF':3,'C':4,'G':1,'F':3}
 base=bases.get(pos,2)
 height=0
 h=(rp[4] if len(rp)>4 else '') or ''
 m=re.search(r"(\d+)'\s*(\d+)",str(h))
 if m:height=int(m.group(1))*12+int(m.group(2))
 ast=number(row.get('ast')) or 0
 return (base,height,-ast,int(pid))
def add(target,key,n=1):
 target[key]=target.get(key,0)+n
def event_stats(ev,frame=None):
 k=kind(ev)
 if not k or k=='sub':return {}
 made=make_status(ev)
 if k=='shot':
  three=shot_three(ev);out={'fga':1,'threeA' if three else 'twoA':1}
  if made:
   out.update({'fgm':1,'threeM' if three else 'twoM':1,'pts':3 if three else 2})
   if str(ev.get('athlete_id_2') or '').isdigit():out['ast']=1
  x=number(ev.get('coordinate_x'));y=number(ev.get('coordinate_y'))
  pt=court_candidate(x,y,frame) if x is not None and y is not None else None
  if pt is not None:
   zone={'Rim':'rim','Short Paint':'paint','Midrange':'mid',
         'Corner 3':'corner','Above Break 3':'above','Deep 3':'deep'}[zone_for(*pt,three)]
   out[zone+'A']=1
   if made:out[zone+'M']=1
  return out
 if k=='ft':return {'fta':1,**({'ftm':1,'pts':1} if made else {})}
 return {k:1}
def lineup_game(gid,events,box,shots,roster):
 teams=sorted(set(r['team'] for r in box.values()))
 if len(teams)!=2:return None,'not_two_teams'
 if shots is None:return None,'unverified_box_shots'
 starting={t:set(pid for pid,r in box.items() if r['team']==t and r['started']) for t in teams}
 if any(len(s)!=5 for s in starting.values()):return None,'not_five_starters'
 for team in teams:
  if abs(sum(r['minutes'] for r in box.values() if r['team']==team)-200)>35 and max(integer(e.get('period_number')) or 2 for e in events)<=2:
   return None,'team_box_minutes_invalid'
 times=[]
 for i,ev in enumerate(events):
  parsed=elapsed(ev)
  if parsed is None:return None,'bad_clock'
  base,seconds=parsed
  times.append((base+seconds,i,ev))
 times.sort(key=lambda x:(x[0],x[1]))
 frame=coordinate_frame(events) # compute once per game, not per play/player
 periods=[integer(e.get('period_number')) for e in events]
 last=max(periods)
 if set(range(1,last+1))-set(periods):return None,'ambiguous_period'
 total=2400+max(0,last-2)*300
 active={t:set(v) for t,v in starting.items()}
 observed=collections.defaultdict(float)
 role_seconds=collections.defaultdict(lambda:[0.0]*5)
 running={}
 game_seconds=0.0
 valid_stat=collections.defaultdict(lambda:{'off':zero(),'def':zero()})
 def accumulate(seconds):
  if seconds<0:raise ValueError('bad_time')
  # A batch of substitutions at the SAME clock may transiently pass through
  # 4 or 6 players. No playing time accrues at zero elapsed seconds.
  if seconds<1e-7:return
  for team in teams:
   if len(active[team])!=5:raise ValueError('not_five_active')
   ordering=sorted(active[team],key=lambda pid:role_sort(pid,box,roster))
   for role,pid in enumerate(ordering):
    observed[pid]+=seconds
    role_seconds[pid][role]+=seconds
 for t,_,ev in times:
  if t+1e-5<game_seconds or t>total+1e-5:return None,'bad_order'
  try:accumulate(t-game_seconds)
  except ValueError:return None,'not_five_active'
  game_seconds=t
  k=kind(ev);team=str(ev.get('team_id') or '')
  if k=='sub':
   if team not in active:return None,'unmatched_substitution_team'
   a=str(ev.get('athlete_id_1') or '');b=str(ev.get('athlete_id_2') or '')
   if a in box and b in box and a!=b and box[a]['team']==team and box[b]['team']==team:
    # Two-participant substitutions: infer only from verified membership.
    if a in active[team] and b not in active[team]:outid,inid=a,b
    elif b in active[team] and a not in active[team]:outid,inid=b,a
    else:return None,'ambiguous_substitution'
    active[team].remove(outid);active[team].add(inid)
   elif a in box and box[a]['team']==team and (not b.isdigit() or b not in box):
    # hoopR archived ESPN PBP frequently represents each substitution as
    # one athlete ("subbing in" / "subbing out"), two rows per same-clock pair.
    desc=str(ev.get('text') or '').lower()
    if 'subbing in' in desc and a not in active[team]:active[team].add(a)
    elif 'subbing out' in desc and a in active[team]:active[team].remove(a)
    else:return None,'ambiguous_substitution'
   else:return None,'unmatched_substitution_ids'
   continue
  stats=event_stats(ev,frame)
  if not stats or team not in teams:continue
  if any(len(active[side_team])!=5 for side_team in teams):
   return None,'incomplete_substitution_batch'
  for side_team in teams:
   # A defensive rebound, steal, block or defensive foul belongs on the
   # defending side. Offense-side DREB are the OPPONENT's defensive boards.
   defensive_event=(k in ('dreb','stl','blk') or
       (k=='pf' and 'offensive foul' not in str(ev.get('text') or '').lower()))
   which=('def' if side_team==team else 'off') if defensive_event else ('off' if side_team==team else 'def')
   for pid,r in box.items():
    if r['team']!=side_team:continue
    d=running.setdefault(pid,{'on':{'off':zero(),'def':zero()},'off':{'off':zero(),'def':zero()}})
    target=d['on' if pid in active[side_team] else 'off'][which]
    for key,v in stats.items():add(target,key,v)
 try:accumulate(total-game_seconds)
 except ValueError:return None,'not_five_active'
 # Every player's reconstructed time must agree with ESPN's per-game box.
 # This also catches missing substitutions, wrong athlete ordering or gaps.
 for pid,r in box.items():
  recon=observed[pid]/60
  if abs(recon-r['minutes'])>max(1.75,.05*r['minutes']):return None,'minutes_disagreement'
 for team in teams:
  total_box=sum(r['minutes'] for r in box.values() if r['team']==team)
  if abs(total_box-total/60*5)>12:return None,'team_minutes_disagreement'
  points=sum(integer(r.get('team_score')) or 0 for r in box.values() if r['team']==team)
  scores=[r['team_score'] for r in box.values() if r['team']==team and r['team_score'] is not None]
  if scores and max(scores)!=min(scores):return None,'box_score_inconsistent'
  if scores:
   score=sum(event_stats(ev).get('pts',0) for ev in events if str(ev.get('team_id'))==team)
   if abs(score-scores[0])>1:return None,'pbp_box_score_disagreement'
 out={}
 for pid,r in box.items():
  stats=running.get(pid,{'on':{'off':zero(),'def':zero()},'off':{'off':zero(),'def':zero()}})
  on=observed[pid]/60
  stats['on']['minutes']=round(on,4)
  stats['off']['minutes']=round(total/60-on,4)
  out[pid]={'stats':stats,'positions':[round(z/60,5) for z in role_seconds[pid]],
            'boxMinutes':r['minutes'],'teamId':r['team']}
 return out,None
def consolidate(cache,roster):
 shots=collections.defaultdict(list);onoff={};positions=collections.defaultdict(lambda:{'roles':[0.0]*5,'box':0.0,'games':0,'known':0.0})
 game_shots=0;game_lineups=0
 for path in sorted(cache.glob('*.json')):
  obj=json.loads(path.read_text())
  if obj.get('schemaVersion')!=1 or obj.get('season')!=2027:continue
  shot=obj.get('shots')
  if shot is not None:
   game_shots+=1
   for pid,rows in shot.items():shots[pid].extend(rows)
  lineup=obj.get('lineup')
  if not lineup:continue
  game_lineups+=1
  for pid,p in lineup.items():
   bucket=onoff.setdefault(pid,{'on':{'off':zero(),'def':zero(),'minutes':0.},'off':{'off':zero(),'def':zero(),'minutes':0.},'games':0,'teamIds':set(),'verifiedBoxMinutes':0.})
   for state in ('on','off'):
    bucket[state]['minutes']+=p['stats'][state]['minutes']
    for side in ('off','def'):
     for k,v in p['stats'][state][side].items():add(bucket[state][side],k,v)
   bucket['games']+=1
   bucket['teamIds'].add(p['teamId'])
   bucket['verifiedBoxMinutes']+=p['boxMinutes']
   q=positions[pid];q['games']+=1;q['box']+=p['boxMinutes']
   for j,val in enumerate(p['positions']):q['roles'][j]+=val
 for pid,v in onoff.items():
  v['teamIds']=sorted(v['teamIds'])
  v['verifiedBoxMinutes']=round(v['verifiedBoxMinutes'],3)
  for state in ('on','off'):v[state]['minutes']=round(v[state]['minutes'],4)
 bypos={}
 for pid,q in positions.items():
  roles=[round(x,4) for x in q['roles']]
  verified=round(sum(roles),4);full=round(q['box'],4)
  if verified<10 or verified>full+max(2,full*.04):continue
  bypos[pid]=[roles,verified,full,q['games'],0.5]
 return shots,onoff,bypos,game_shots,game_lineups
def publish(root=ROOT):
 data=root/'data'
 src=data/'advanced_2027_pbp/games'
 boxpath=data/'advanced_2027_player_box.csv.gz'
 cache=data/'advanced_2027_verified_games'
 cache.mkdir(parents=True,exist_ok=True)
 roster_path=data/'roster_2027_advanced.json'
 roster=json.loads(roster_path.read_text())['players'] if roster_path.exists() else []
 roster={str(p[0]):p for p in roster if isinstance(p,list) and p}
 rejected=collections.Counter();new=0
 boxgames=load_box(boxpath) if boxpath.exists() else {}
 for file in sorted(src.glob('*.csv.gz')) if src.exists() else []:
  gid=file.name[:-7] # *.csv.gz, strip extension
  if not gid.isdigit():continue
  target=cache/(gid+'.json')
  previous=json.loads(target.read_text()) if target.exists() else None
  # Keep fully verified releases immutable; retry only missing advanced
  # components when archived PBP/collector format later improves.
  if previous and previous.get('shots') is not None and previous.get('lineup') is not None:continue
  box=boxgames.get(gid)
  if not box:
   rejected['box_missing']+=1;continue
  try:
   events=read_csv(file)
   if len(events)<50:raise ValueError('pbp_too_short')
   shot,reason=shot_game(gid,events,box)
   if previous and previous.get('shots') is not None:shot=previous['shots'];reason=None
   if reason:rejected[reason]+=1
   lineup,lreason=lineup_game(gid,events,box,shot,roster) if shot is not None else (None,'shot_unverified')
   if previous and previous.get('lineup') is not None:lineup=previous['lineup'];lreason=None
   if lreason:rejected[lreason]+=1
   if shot is None and lineup is None:continue
   if previous and previous.get('lineup') is None and lineup is None:continue
   save_json(target,{'schemaVersion':1,'season':SEASON,'gameId':gid,'shots':shot,
                     'lineup':lineup,'qa':{'shotsVerified':shot is not None,'lineupVerified':lineup is not None}})
   new+=1
  except Exception as e:
   rejected['parse_exception_'+type(e).__name__]+=1
 # Opening-week fail-closed: no verified ESPN game means no fabricated
 # "available" feed, manifest, or 128 empty player shards.
 if not any(cache.glob('*.json')):
  print(json.dumps({'status':'NO_VERIFIED_2027_ADVANCED_GAMES','newCachedGames':0,
                    'excluded':dict(rejected)},sort_keys=True))
  return {'shotGames':0,'lineupGames':0,'rejected':dict(rejected)}
 shots,onoff,positions,ns,nl=consolidate(cache,roster)
 teams=json.loads(roster_path.read_text()).get('teams',{}) if roster_path.exists() else {}
 published=root/'public'
 configs=[('portal_shots_2027','shots',shots),('portal_onoff_2027','onoff',onoff),('portal_positions_2027','positions',positions)]
 for directory,stem,byid in configs:
  dest=published/directory
  dest.mkdir(parents=True,exist_ok=True)
  # Write shards only if real verified records exist, never fabricate players.
  if byid:
   buckets=collections.defaultdict(dict)
   for pid,rec in byid.items():buckets[int(pid)%MOD][pid]=rec
   for ix in range(MOD):
    shard={'schemaVersion':1,'season':SEASON,'shard':ix,'modulo':MOD,
           'players':buckets[ix]}
    if stem=='shots':shard['fields']=SHOT_FIELDS
    save_json(dest/(stem+'_'+str(ix).zfill(3)+'.json'),shard)
  manifest={'schemaVersion':1,'season':SEASON,'seasonLabel':'2026-27',
            'modulo':MOD,'available':bool(byid),
            'source':'ESPN 2026-27 PBP + game-level verified ESPN box IDs',
            'gamesInSource':len(list(src.glob('*.csv.gz'))) if src.exists() else 0,
            'gamesVerified':ns if stem=='shots' else nl,
            'sampleIsPartial':True,
            'method':'Per-game complete ESPN box validation; unverified games excluded',
            'qa':{'verifiedShotGames':ns,'verifiedFivePlayerGames':nl,
                  'newlyVerifiedGames':new,'rejectedReasons':dict(rejected)}}
  if stem=='shots':
   manifest.update(complete=False,teams=teams,playerCoverageFlags={},
                   playersWithShots=len(byid),minimumPlayerCoverage='Full FGA/FGM/3PA/3PM matches per included game')
  if stem=='positions':
   manifest.update(playersWithRoleTime=len(byid),minimumDisplayMinutes=10,
                   warnings='Role assigned by position/height/assist hierarchy over validated five-player stints; not tracking-based')
  if stem=='onoff':
   manifest.update(playersWithVerifiedGameSplits=len(byid),
                   limitation='Descriptive lineup-based stats, no causal or opponent adjustment; incomplete game coverage')
  save_json(dest/'manifest.json',manifest)
 print(json.dumps({'status':'PASS','newCachedGames':new,'shotsGames':ns,
     'lineupGames':nl,'playersWithShots':len(shots),'playersWithOnOff':len(onoff),
     'playersWithPositions':len(positions),'excluded':dict(rejected)},sort_keys=True))
 return {'shotGames':ns,'lineupGames':nl,'rejected':dict(rejected)}
if __name__=='__main__':
 publish(pathlib.Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT)
