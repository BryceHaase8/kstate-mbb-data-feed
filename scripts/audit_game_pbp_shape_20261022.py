#!/usr/bin/env python3
import json,urllib.request,datetime,collections,pathlib
ids=['401825507','401827153']
out={'generated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'games':{}}
for id in ids:
 try:
  url=f'https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/summary?event={id}'
  req=urllib.request.Request(url,headers={'Accept':'application/json','Origin':'https://portal-site-test.netlify.app','User-Agent':'Mozilla/5.0'})
  with urllib.request.urlopen(req,timeout=30) as r:raw=json.load(r)
  keys={k:('list '+str(len(v)) if isinstance(v,list) else 'object '+str(len(v)) if isinstance(v,dict) else str(type(v).__name__)) for k,v in raw.items()}
  lists={k:len(v) for k,v in raw.items() if isinstance(v,list)}
  plays=raw.get('plays') or []
  if isinstance(plays,dict):
   plays=plays.get('plays') or plays.get('all') or []
  d={'keys':keys,'lists':lists,'plays_count':len(plays),'first_plays':plays[:5],
     'last_plays':plays[-4:],'box_player_count':len(raw.get('boxscore',{}).get('players',[])),
     'has_game_info':bool(raw.get('gameInfo'))}
  text=json.dumps(d,ensure_ascii=False,default=str)
  # Keep saved report <= 65k to facilitate followup inspection
  out['games'][id]={'keys':keys,'plays_count':len(plays),'first_plays':plays[:4],
    'last_plays':plays[-3:],
    'event_fields':dict(collections.Counter(k for p in plays for k in p)),
    'shooting_play':next((p for p in plays if p.get('shootingPlay') or (p.get('type') or {}).get('text','').lower().find('shot')>=0),None),
    'substitution_play':next((p for p in plays if 'substit' in str(p.get('text','')).lower() or 'sub' in str((p.get('type') or {}).get('text','')).lower()),None)}
 except Exception as e:out['games'][id]={'error':str(e)}
path=pathlib.Path('research_qa/games/2026_game_pbp_shape_20261022.json')
path.parent.mkdir(parents=True,exist_ok=True)
path.write_text(json.dumps(out,indent=2,ensure_ascii=False,default=str)[:150000])
print(json.dumps({id:{'n':x.get('plays_count'),'error':x.get('error'),'fields':x.get('event_fields')} for id,x in out['games'].items()}))
