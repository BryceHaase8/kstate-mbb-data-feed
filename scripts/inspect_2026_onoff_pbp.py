#!/usr/bin/env python3
import urllib.request,pathlib,json,collections
import pandas as pd
p=pathlib.Path('/tmp/pbp2026.parquet')
if not p.exists():
    url='https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_mens_college_basketball_pbp/play_by_play_2026.parquet'
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'PortalResearch/1.0'}),timeout=120) as response:p.write_bytes(response.read())
d=pd.read_parquet(p)
print('DATA',json.dumps({'rows':len(d),'cols':list(d.columns),'bytes':int(p.stat().st_size)}))
for name in ['type_text','event_type','type_id','home_away','team_id','athlete_id_1','athlete_id_2','period_number','scoring_play','score_value','shot_made','text','end_period_seconds_remaining','coordinate_x','coordinate_y','sequence_number']:
    if name not in d:continue
    x=d[name]
    if name in ('text',):print('TEXT',d['text'].dropna().astype(str).sample(n=min(15,len(d)),random_state=7).tolist());continue
    print('FIELD',name,'null',int(x.isna().sum()),'values',json.dumps(x.astype(str).value_counts(dropna=False).head(22).to_dict()))
subs=d[d.type_text.astype(str).str.contains('Substitution',case=False,na=False)]
print('SUBSTITUTIONS',len(subs))
print('SUBSAMPLES',json.dumps(subs[['game_id','team_id','athlete_id_1','athlete_id_2','type_text','text','period_number','end_period_seconds_remaining']].head(20).fillna('').astype(str).to_dict('records')))
print('GAME SAMPLE',json.dumps(d[d.game_id==d.game_id.dropna().iloc[50]][[k for k in ['game_id','period_number','clock_display_value','type_text','event_type','team_id','athlete_id_1','athlete_id_2','text','home_score','away_score'] if k in d]].head(25).fillna('').astype(str).to_dict('records')))
