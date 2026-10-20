import pandas as pd, urllib.request, pathlib, json
p=pathlib.Path('/tmp/pbp2026.parquet')
url='https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_mens_college_basketball_pbp/play_by_play_2026.parquet'
if not p.exists():
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Portal-Research/1.0'}),timeout=160) as h:p.write_bytes(h.read())
df=pd.read_parquet(p)
print('PBP_ROWS',len(df),'COLUMNS',list(df.columns))
for name in ['type_text','event_type','text','athlete_id_1','athlete_id_2','team_id','home_team_id','away_team_id','sequence_number','game_id','period_number','clock_display_value','shot_made','score_value']:
 if name not in df: continue
 x=df[name]
 print('FIELD',name,'nonNull',int(x.notna().sum()),'unique',x.nunique(dropna=True),'examples',x.dropna().astype(str).value_counts().head(12).to_dict())
g=df[df.game_id.astype(str).str.contains('401856563')]
if g.empty:g=df.head(500)
print('SAMPLE_GAME',str(g.game_id.iloc[0]),'events',len(g))
col=[c for c in ['sequence_number','period_number','clock_display_value','type_text','event_type','text','athlete_id_1','athlete_id_2','team_id','home_team_id','away_team_id','score_value'] if c in g]
print('SAMPLE_SUBS',json.dumps(g[g.type_text.astype(str).str.contains('Substitution',case=False)][col].head(25).fillna('').astype(str).to_dict('records')))
print('SAMPLE_START',json.dumps(g[col].head(16).fillna('').astype(str).to_dict('records')))
