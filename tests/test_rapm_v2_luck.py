#!/usr/bin/env python3
"""Synthetic deterministic basketball possession test: luck-adjusted points and observed points remain distinct."""
import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from rapm_possessions_v2 import run_one
h="101|102|103|104|105"; a="201|202|203|204|205"
events=[
(1200,"","Jumpball","Start game",0,0,"", "", ""),
(1190,"H","2PT Shot","Home player makes 24 foot three point jumper",3,0,"101","TRUE","3"),
(1180,"A","2PT Shot","Away player misses three point jumper",3,0,"201","FALSE","3"),
(1179,"H","Rebound","Home player Defensive Rebound",3,0,"101", "", ""),
(1165,"H","MadeFreeThrow","Home player misses free throw 1 of 1",3,0,"101","FALSE","2"),
(1164,"A","Rebound","Away player Defensive Rebound",3,0,"201", "", ""),
(1140,"A","MadeFreeThrow","Away player makes free throw 1 of 1",3,1,"201","TRUE","2"),
(0,"","End Period","End Period",3,1,"", "", "")
]
rows=[{"game_id":"sample","period_number":1,"seconds_remaining_period":t,
"home_team_id":"H","away_team_id":"A","team_id":team,"event_type":typ,
"text":desc,"home_score":home,"away_score":away,"athlete_id_1":pid,
"shot_made":made,"shot_value":sv} for t,team,typ,desc,home,away,pid,made,sv in events]
indexed={("sample",1):[{"start_remaining":1200,"end_remaining":0,
                              "home_players":h,"away_players":a}]}
p,_,_,_=run_one("sample",pd.DataFrame(rows),indexed,{
"three":{"101":.40,"201":.30},"ft":{"101":.70,"201":.80},
"defaultThree":.337,"defaultFT":.722})
assert len(p)==4,p
observed=[x["points"] for x in p]
expected=[x["pointsLuckAdjusted"] for x in p]
assert observed==[3,0,0,1],observed
for i,(got,want) in enumerate(zip(expected,[1.2,.9,.7,.8])):
    assert abs(got-want)<1e-9,(i,got,want)
assert sum(x["luck3Attempts"] for x in p)==2
assert sum(x["luckFTAttempts"] for x in p)==2
assert all(len(x["off_players"].split("|"))==5 for x in p)
print("PASS: score reconciliation, 3PT/FT makes and misses, posterior expectation corrections, and five-man lineups")
