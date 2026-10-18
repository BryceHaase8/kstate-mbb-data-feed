"""Research-only NCAA->ESPN identity crosswalk tests. Never infer by name alone."""
import sys,pandas as pd
sys.path.insert(0,"scripts")
from v4_archive_rapm_ablation import match_ncaa_to_espn,team_agrees,ncaaplayer_name
assert ncaaplayer_name("BOOZER.CAMERON")=="cameronboozer"
assert team_agrees("Duke Blue Devils","Duke")
assert not team_agrees("Miami Hurricanes","Miami (OH)")
espn=pd.DataFrame([
  {"athlete_id":"101","player_name":"Cameron Boozer","team_name":"Duke Blue Devils"},
  {"athlete_id":"102","player_name":"Jordan Smith","team_name":"Indiana Hoosiers"},
  {"athlete_id":"103","player_name":"Jordan Smith","team_name":"Iona Gaels"},
  {"athlete_id":"104","player_name":"Alex Carter","team_name":"Miami Hurricanes"},
  {"athlete_id":"105","player_name":"Isaiah Jones","team_name":"South Florida Bulls"}])
ncaa=pd.DataFrame([
  {"player":"BOOZER.CAMERON","team":"Duke","rapm_net":3.2,"off_poss":1000,"def_poss":1000},
  {"player":"SMITH.JORDAN","team":"Indiana","rapm_net":6,"off_poss":1200,"def_poss":1000},
  {"player":"CARTER.ALEX","team":"Miami (OH)","rapm_net":8,"off_poss":1200,"def_poss":1000},
  {"player":"JONES.ISAIAH","team":"South Florida","rapm_net":1,"off_poss":1000,"def_poss":1000}])
m,q=match_ncaa_to_espn(espn,ncaa)
assert set(m.loc[m.matchedRapm,"athlete_id"])=={"101","105"}
assert m.athlete_id.nunique()==len(m)
print("PASS crosswalk: exact unique name AND verified team, rejects homonyms/wrong Miami, preserves unmatched IDs")
