#!/usr/bin/env python3
import urllib.request, json, pathlib, datetime
u='https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard?dates=20260206&groups=50&limit=500'
report={'url':u,'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'origins':[]}
for o in ['https://portal-site-test.netlify.app','http://localhost:8000','null']:
 try:
  req=urllib.request.Request(u,headers={'Origin':o,'Accept':'application/json','User-Agent':'python-urllib/3.11'})
  with urllib.request.urlopen(req,timeout=20) as r:
   raw=r.read(); obj=json.loads(raw)
   report['origins'].append({'origin':o,'status':r.status,'allow_origin':r.headers.get('Access-Control-Allow-Origin'),'vary':r.headers.get('Vary'),'event_count':len(obj.get('events') or []),'byte_count':len(raw)})
 except Exception as e:report['origins'].append({'origin':o,'error':str(e)[:400]})
# Probe whether ESPN returns all games for a full month date-range query.
month_url='https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard?dates=20260201-20260228&groups=50&limit=2000'
try:
 with urllib.request.urlopen(urllib.request.Request(month_url,headers={'Origin':'http://localhost:8000','Accept':'application/json','User-Agent':'Mozilla/5.0'}),timeout=30) as r:
  data=json.load(r)
  dates=sorted(set(str(g.get('date',''))[:10] for g in data.get('events',[])))
  report['month_range']={'events':len(data.get('events',[])),'distinct_utc_dates':len(dates),'first_dates':dates[:6],'last_dates':dates[-6:],'cors':r.headers.get('Access-Control-Allow-Origin')}
except Exception as e:report['month_range']={'error':str(e)[:300]}
for label,spec in [('month_short','202602'),('month_full','20260201-20260228'),('month_compact','20260201_20260228')]:
 try:
  address=f'https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard?dates={spec}&groups=50&limit=2000'
  with urllib.request.urlopen(urllib.request.Request(address,headers={'Origin':'http://localhost:8000','User-Agent':'Mozilla/5.0'}),timeout=25) as r:
   data=json.load(r)
   dates=sorted(set(str(g.get('date',''))[:10] for g in data.get('events',[])))
   report[label]={'events':len(data.get('events',[])),'distinct_utc_dates':len(dates),'first_dates':dates[:3],'last_dates':dates[-3:]}
 except Exception as e:report[label]={'error':str(e)[:110]}
path=pathlib.Path('research_qa/espn_game_browser_cors_20261022.json');path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
