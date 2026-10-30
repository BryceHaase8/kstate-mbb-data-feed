import json,subprocess,urllib.request,time,concurrent.futures as cf,pathlib,datetime
subprocess.run(['git','fetch','--depth=1','origin','staging-seven-year-history-2027-roster-identity'],check=True)
b=json.loads(subprocess.check_output(['git','show','FETCH_HEAD:research_data/staged/roster_2027_fast_ready.json']))
teams={str(k):v for k,v in b['teams'].items()}; old={str(p[0]):{'name':p[1],'teamId':str(p[2]),'team':teams.get(str(p[2])),'elig':p[6]} for p in b['players']}
def flatten(x):
 if isinstance(x,list):
  return [y for z in x for y in flatten(z)]
 if isinstance(x,dict):
  if x.get('id') and (x.get('displayName') or x.get('fullName')):return [x]
  return [y for key in ('items','athletes','players','roster') for y in flatten(x.get(key,[]))]
 return []
def get(pair):
 tid,team=pair;url=f'https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams/{tid}/roster?season=2027'
 for i in range(3):
  try:
   req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})
   with urllib.request.urlopen(req,timeout=12) as f:d=json.load(f)
   s=d.get('season') or {};year=s.get('year') if isinstance(s,dict) else None
   if year and int(year)!=2027:raise ValueError('wrong ESPN season '+str(year))
   aa=flatten(d.get('athletes') or d.get('roster') or []);p={str(a['id']):{'name':a.get('displayName') or a.get('fullName'),'teamId':tid,'team':team} for a in aa if str(a.get('id','')).isdigit()}
   if not 4<=len(p)<=32:raise ValueError('unexpected roster size '+str(len(p)))
   return tid,p,None
  except Exception as e:
   error=str(e)
   if i<2:time.sleep(i+1)
 return tid,{},error
fresh={};ok=set();fails=[]
with cf.ThreadPoolExecutor(max_workers=7) as pool:
 for tid,players,error in pool.map(get,teams.items()):
  if error:fails.append({'team':teams[tid],'error':error[:160]})
  else:ok.add(tid);fresh.update(players)
prev={k:v for k,v in old.items() if v['teamId'] in ok};new={k:v for k,v in fresh.items() if v['teamId'] in ok}
added=sorted([dict(espnId=k,**v) for k,v in new.items() if k not in old],key=lambda p:(p['team'],p['name'] or ''))
removed=sorted([dict(espnId=k,**v) for k,v in prev.items() if k not in fresh],key=lambda p:(p['team'],p['name'] or ''))
moved=sorted([{'espnId':k,'name':v['name'],'from':old[k]['team'],'to':v['team']} for k,v in new.items() if k in old and old[k]['teamId']!=v['teamId']],key=lambda p:p['name'] or '')
report={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'season':2027,'expectedTeams':len(teams),'fetchedTeams':len(ok),'baselinePlayers':len(old),'fetchedUniquePlayers':len(fresh),'new':added,'removed':removed,'moved':moved,'failures':fails,'note':'ESPN presence is not proof of NCAA eligibility; only successfully fetched teams compared; production untouched'}
pathlib.Path('roster_audit_20261030.json').write_text(json.dumps(report,indent=2))
summary={k:report[k] for k in ('utc','season','expectedTeams','fetchedTeams','baselinePlayers','fetchedUniquePlayers')};summary.update({'new':len(added),'removed':len(removed),'moved':len(moved),'failures':len(fails)})
print('SUMMARY '+json.dumps(summary),flush=True)
for label,rows in [('NEW',added),('REMOVED',removed),('MOVED',moved),('FAILURES',fails)]:print(label+' '+json.dumps(rows[:80]),flush=True)
print('COVERAGE', 'PASS' if len(ok)>=330 and len(fresh)>=4000 else 'FAIL - no national claims',flush=True)
