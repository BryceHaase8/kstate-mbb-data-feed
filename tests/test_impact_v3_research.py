import json,sys,numpy as np,pandas as pd
sys.path.insert(0,"scripts")
from impact_v3_research import features_from_espn,bpm_proxy
p=json.load(open("research_qa/ebpm_v3_coefficients.json"))
row={"gp":35,"mpg":30,"ppg":18,"rpg":7,"apg":3,"spg":1,"bpg":1,"topg":2,
"two_pa_pg":10,"three_pa_pg":4,"fta_pg":5,"two_pm":210,"three_pm":56,"ftm":140,
"two_pt_pct":0.6,"three_pt_pct":0.4,"ft_pct":0.8,"efg_pct":0.54,"ts_pct":0.59}
v=bpm_proxy(features_from_espn(pd.DataFrame([row])),p)
assert np.isfinite(v).all(),v
print("V3 TEST PASS",v)
