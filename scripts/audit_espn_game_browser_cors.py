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
path=pathlib.Path('research_qa/espn_game_browser_cors_20261022.json');path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
