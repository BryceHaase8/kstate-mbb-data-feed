#!/usr/bin/env python3
"""End-to-end synthetic ESPN 2026–27 game QA. No mocked live NCAA outcomes."""
import csv,gzip,json,pathlib,sys,tempfile,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from publish_2027_advanced import publish,shot_game,lineup_game,parse_seconds,kind,shot_three

def fixture(root, bad_sub=False, bad_shot=False, no_shots=False):
 base=pathlib.Path(root);(base/'data/advanced_2027_pbp/games').mkdir(parents=True)
 teams={'100':'A','200':'B'}
 athletes=[]
 for t in teams:
  for i,pos in enumerate(['G','G','F','F','C']):
   athletes.append({'game_id':'401900001','athlete_id':str(int(t)*100+i),
       'team_id':t,'started':'1','minutes':'40',
       'fga':'1' if i==0 else '0','fgm':'1' if i==0 and t=='100' else '0',
       'three_pa':'1' if i==0 and t=='100' else '0',
       'three_pm':'1' if i==0 and t=='100' else '0',
       'team_score':'','position':pos,'ast':'0','reb':'0'})
 f=base/'data/advanced_2027_player_box.csv.gz'
 with gzip.open(f,'wt',newline='') as fp:
  w=csv.DictWriter(fp,fieldnames=athletes[0]);w.writeheader();w.writerows(athletes)
 (base/'data/roster_2027_advanced.json').write_text(json.dumps({
   'players':[[x['athlete_id'],'Athlete '+x['athlete_id'],x['team_id'],x['position'],"6' 4\""] for x in athletes],
   'teams':{'100':'Team A','200':'Team B'}}))
 def ev(p,clock,typ,text,tid='',a='',b='',x='',y='',sc='0'):
  return {'game_id':'401900001','sequence_number':str(len(events)+1),
          'period_number':str(p),'clock_display_value':clock,
          'type_text':typ,'text':text,'team_id':tid,'athlete_id_1':a,'athlete_id_2':b,
          'coordinate_x':x,'coordinate_y':y,'score_value':sc}
 events=[]
 events.append(ev(1,'20:00','Period Start','First half begins'))
 if not no_shots:
  events.append(ev(1,'19:00','Made Shot','Athlete makes 23-foot 3-point jumper','100','10000',x='2' if not bad_shot else '',y='1',sc='3'))
  events.append(ev(1,'18:00','Missed Shot','Athlete misses 2-foot layup','200','20000',x='25',y='1'))
 if bad_sub:
  events.append(ev(1,'17:00','Substitution','Player enters the game for player','100','10001','10002'))
 for i in range(50):
  events.append(ev(1,'16:00','Timeout','Dead ball'))
 events.append(ev(2,'20:00','Period Start','Second half begins'))
 events.append(ev(2,'0:00','Period End','Game complete'))
 p=base/'data/advanced_2027_pbp/games/401900001.csv.gz'
 with gzip.open(p,'wt',newline='') as fp:
  w=csv.DictWriter(fp,fieldnames=events[0]);w.writeheader();w.writerows(events)
 return base,p
class AdvancedPublisherTests(unittest.TestCase):
 def test_type_and_clock(self):
  self.assertEqual(parse_seconds('19:59'),1199)
  self.assertIsNone(parse_seconds('19:99'))
  self.assertEqual(kind({'type_text':'Substitution','text':'in for'}),'sub')
  self.assertEqual(kind({'type_text':'Made Shot','text':'A makes 3-point jumper'}),'shot')
  self.assertTrue(shot_three({'text':'A misses 3-point jumper'}))
  self.assertIsNone(kind({'text':'Coach timeout','type_text':'Timeout'}))
 def test_three_publishers_same_verified_game(self):
  with tempfile.TemporaryDirectory() as root:
   base,_=fixture(root)
   r=publish(base)
   self.assertEqual((r['shotGames'],r['lineupGames']),(1,1))
   pub=base/'public'
   shot=json.loads((pub/'portal_shots_2027/shots_016.json').read_text())
   self.assertEqual(shot['fields'],['gameId','teamId','opponentId','shotValue','made','courtX','courtY','assistId','zone'])
   # ESPN ID 10000 modulo 128 = 16; 20000 modulo 128 = 32.
   self.assertEqual(shot['players']['10000'][0],[ '401900001','100','200',3,1,-23.0,6.25,None,'Corner 3'])
   oo=json.loads((pub/'portal_onoff_2027/onoff_016.json').read_text())
   self.assertEqual(oo['players']['10000']['games'],1)
   self.assertAlmostEqual(oo['players']['10000']['on']['minutes'],40)
   self.assertEqual(oo['players']['10000']['on']['off']['fga'],1)
   self.assertEqual(oo['players']['10000']['on']['def']['fga'],1)
   pos=json.loads((pub/'portal_positions_2027/positions_016.json').read_text())['players']['10000']
   self.assertEqual(len(pos),5)
   self.assertEqual(len(pos[0]),5)
   self.assertAlmostEqual(sum(pos[0]),40)
   self.assertEqual(pos[3],1)
   self.assertEqual(json.loads((pub/'portal_shots_2027/manifest.json').read_text())['complete'],False)
   self.assertEqual(json.loads((pub/'portal_onoff_2027/manifest.json').read_text())['gamesVerified'],1)
   self.assertEqual(json.loads((pub/'portal_positions_2027/manifest.json').read_text())['playersWithRoleTime'],10)
   self.assertEqual(publish(base)['lineupGames'],1) # immutable day-to-day cache, no duplication
 def test_ambiguous_substitutions_reject_lineup_not_valid_shots(self):
  with tempfile.TemporaryDirectory() as root:
   base,_=fixture(root,bad_sub=True)
   m=publish(base)
   self.assertEqual((m['shotGames'],m['lineupGames']),(1,0))
   self.assertEqual(m['rejected']['ambiguous_substitution'],1)
   self.assertFalse(json.loads((base/'public/portal_onoff_2027/manifest.json').read_text())['available'])
 def test_coordinate_gap_rejects_shots_and_all_derived_stints(self):
  with tempfile.TemporaryDirectory() as root:
   base,_=fixture(root,bad_shot=True)
   m=publish(base)
   self.assertEqual((m['shotGames'],m['lineupGames']),(0,0))
   self.assertEqual(m['rejected']['shot_coordinates_missing_or_changed'],1)
   self.assertFalse((base/'public/portal_shots_2027/manifest.json').exists())
   self.assertEqual(list((base/'data/advanced_2027_verified_games').glob('*.json')),[])
 def test_archive_lengthwise_court_frame_detected_without_guessing(self):
  from publish_2027_advanced import coordinate_frame,court_candidate
  events=[{'type_text':'Made Shot','text':'Athlete makes 2-foot layup',
           'coordinate_x':'43','coordinate_y':'2'}]
  self.assertEqual(coordinate_frame(events),'lengthwise')
  self.assertEqual(court_candidate(43,2,'lengthwise'),(2,4))
 def test_missing_pbps_publish_explicit_unavailable_manifests(self):
  with tempfile.TemporaryDirectory() as root:
   base=pathlib.Path(root)
   m=publish(base)
   self.assertEqual((m['shotGames'],m['lineupGames']),(0,0))
   for kind in ('shots','onoff','positions'):
    self.assertFalse((base/f'public/portal_{kind}_2027/manifest.json').exists())

if __name__=='__main__':unittest.main()
