import csv,gzip,importlib.util,json,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('advanced',Path(__file__).parent/'build_2027_advanced.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class TestAdvanced(unittest.TestCase):
 def writecsv(self,path,rows):
  path.parent.mkdir(parents=True,exist_ok=True)
  with gzip.open(path,'wt',newline='') as f:
   w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 def test_synthetic_two_halves(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   box=[];names=[]
   for team in ('111','222'):
    for n in range(5):
     pid=str(5000000+int(team)*10+n)
     box.append({'game_id':'401999999','team_id':team,'athlete_id':pid,'started':'1',
        'minutes':'40','fga':'12','position':['PG','SG','SF','PF','C'][n]})
     names.append(pid)
   self.writecsv(root/'box.csv.gz',box)
   p=[]
   for period in (1,2):
    for k in range(60):
     team='111' if k%2 else '222'
     pid=str(5000000+int(team)*10+(k%5))
     p.append({'game_id':'401999999','sequence_number':str((period-1)*60+k),
       'period_number':str(period),'clock_display_value':f'{max(0,20-(k//3)):02d}:00',
       'type_text':'JumpShot','text':'jump shot','team_id':team,
       'athlete_id_1':pid,'athlete_id_2':'','scoring_play':'True',
       'score_value':'2','home_team_id':'111','away_team_id':'222',
       'coordinate_x':'43','coordinate_y':'2'})
   self.writecsv(root/'pbp'/'401999999.csv.gz',p)
   output=root/'public'
   result=mod.build(mod.source_box(root/'box.csv.gz'),root/'pbp',output)
   self.assertTrue(result['published'],result)
   self.assertGreater(result['shots'],50)
   self.assertGreater(result['onoffPlayers'],0)
   self.assertGreater(result['positionIntervals'],0)
   shot=names[0];shard=int(shot)%128
   d=json.loads((output/'portal_shots_2027'/f'shots_{shard:03d}.json').read_text())
   self.assertEqual(len(d['players'][shot]),12)
   self.assertEqual(d['players'][shot][0][8],'Rim')
   self.assertEqual(json.loads((output/'portal_shots_2027'/'manifest.json').read_text())['season'],2027)
 def test_no_games_does_not_publish_manifest(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);res=mod.build({},root/'missing',root/'public')
   self.assertFalse(res['published'])
   self.assertFalse((root/'public'/'portal_shots_2027'/'manifest.json').exists())
 def test_invalid_location_is_not_fabricated(self):
  e={'game_id':'123','team_id':'111','type_text':'JumpShot','score_value':3,'coordinate_x':'', 'coordinate_y':'4'}
  self.assertIsNone(mod.shot_event(e,'111','222'))
 def test_ambiguous_half_rejected(self):
  events=[{'period_number':2,'clock_display_value':'19:59','team_id':'222','athlete_id_1':'2','type_text':'JumpShot','text':''}]
  self.assertEqual(mod.player_states(events,{'min':15,'started':False},'1','111')[1],'missing_period')
if __name__=='__main__':unittest.main()
