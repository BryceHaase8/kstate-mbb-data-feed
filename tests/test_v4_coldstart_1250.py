"""Hard tests for 1200+ fresh ESPN IDs, absent priors, no minutes, and safe identity."""
import sys,json,numpy as np,pandas as pd
sys.path.insert(0,"scripts")
from v4_coldstart_contract import score_new_season
p=json.load(open("research_qa/ebpm_v3_coefficients.json"))
N=1250
rows=[]
for i in range(N):
    gp,mpg=(0,0) if i<400 else ((3,16) if i<800 else (15,24))
    rows.append(dict(season=2027,athlete_id=f"NEW_{i+1:05d}",player_name=f"Rookie {i}",
     team_id="123",gp=gp,mpg=mpg,ppg=8,rpg=4,apg=2,spg=.7,bpg=.2,topg=1.1,
     two_pa_pg=4,three_pa_pg=3,fta_pg=2,two_pm=gp*2.3,three_pm=gp*1,ftm=gp*1.5,
     two_pt_pct=.55,three_pt_pct=.333,ft_pct=.75,efg_pct=.54,ts_pct=.57))
df=pd.DataFrame(rows)
out=score_new_season(df,p,2027,prior_ratings={"PREVIOUS_001":9})
assert len(out)==N
assert out.athlete_id.is_unique
assert out.is_new_to_history.all()
assert out.rating_status.value_counts().to_dict()=={"established":450,"unscored":400,"provisional":400}
assert out.loc[out.rating_status=="unscored","boxBPM_raw"].isna().all()
assert out.loc[out.rating_status=="provisional","rankable"].eq(False).all()
assert out.loc[out.rating_status=="established","boxBPM_shrunk"].notna().all()
assert out.rapm_used.eq(False).all()
try:score_new_season(pd.concat([df,df.iloc[[0]]]),p,2027)
except ValueError:pass
else:raise AssertionError("Duplicate ESPN ID accepted")
try:score_new_season(df,p,2028)
except ValueError:pass
else:raise AssertionError("Missing season accepted")
print("PASS 1,250 unique new-player cold starts; 400 unscored, 400 provisional, 450 established; fail-closed IDs, no RAPM/network")
