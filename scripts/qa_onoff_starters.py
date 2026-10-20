import gzip,csv,collections,json
from pathlib import Path
file='research_data/historical/game_logs/player_game_logs_2026.csv.gz'
groups=collections.defaultdict(list)
with gzip.open(file,'rt',encoding='utf8',newline='') as f:
 for r in csv.DictReader(f):groups[(r['game_id'],r['team_id'])].append(r)
def yes(x):return str(x).lower() in ('1','true','t','yes')
hist=collections.Counter()
for rows in groups.values():hist[sum(yes(x.get('started')) for x in rows)]+=1
examples={}
for k,rows in groups.items():
 if k[0]=='401804830' or len(examples)<1:
  examples[str(k)]=[{'name':r['player_name'],'athlete_id':r['athlete_id'],'started':r['started'],'minutes':r['minutes']} for r in rows]
print(json.dumps({'teamGames':len(groups),'starterCounts':dict(sorted(hist.items())),'examples':examples},indent=2))
