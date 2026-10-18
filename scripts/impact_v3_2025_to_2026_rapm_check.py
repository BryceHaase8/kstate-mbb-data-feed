#!/usr/bin/env python3
"""Out-of-time historical test of V3's fixed RAPM correction.

Predict 2025-26 box-score impact from 2024-25 player box and RAPM. The
target is the frozen V3 box-BPM proxy on 2025-26 ESPN stats, not Torvik BPM.
No 2026 season statistics enter any 2025 predictor. All samples matched
by ESPN athlete ID, not name. Does not train the RAPM weight on 2026.
"""
import json,sys
from pathlib import Path
import pandas as pd,numpy as np
from sklearn.linear_model import HuberRegressor
from sklearn.metrics import mean_absolute_error
from scipy.stats import spearmanr
sys.path.insert(0,"scripts")
from impact_v3_research import features_from_espn,bpm_proxy,divide

def main():
    params=json.loads(Path("research_qa/ebpm_v3_coefficients.json").read_text())
    raw=pd.read_csv("data/current_player_season_stats.csv",dtype={"athlete_id":str,"team_id":str},low_memory=False)
    raw["season"]=pd.to_numeric(raw.season,errors="coerce")
    seasons={}
    for season in (2025,2026):
        s=raw.loc[raw.season==season].copy()
        s["gp"]=pd.to_numeric(s["gp"],errors="coerce").fillna(0)
        s["mpg"]=pd.to_numeric(s["mpg"],errors="coerce").fillna(0)
        s["estBPM"]=bpm_proxy(features_from_espn(s),params)
        s=s.sort_values(["gp","mpg"],ascending=False).drop_duplicates("athlete_id")
        seasons[season]=s
    base=seasons[2025].merge(seasons[2026],on="athlete_id",suffixes=("_2025","_2026"),validate="one_to_one")
    gp_old=base.gp_2025.to_numpy(float);mpg_old=base.mpg_2025.to_numpy(float)
    gp_new=base.gp_2026.to_numpy(float);mpg_new=base.mpg_2026.to_numpy(float)
    eligible=(gp_old>=15)&(mpg_old>=10)&(gp_new>=10)&(mpg_new>=10)
    model=json.loads(Path("research_qa/rapm_2025_luck_model.json").read_text())
    assert model["season"]==2025
    assert model["cleanPossessions"]>=200000
    rr=pd.DataFrame(model["variants"]["luckAdjusted"])
    rr["espnAthleteId"]=rr.espnAthleteId.astype(str)
    assert rr.espnAthleteId.is_unique
    base=base.merge(rr[["espnAthleteId","totalRAPM","cleanPossessionExposure"]],left_on="athlete_id",right_on="espnAthleteId",how="left",validate="one_to_one")
    now=base.estBPM_2025.to_numpy(float)
    target=base.estBPM_2026.to_numpy(float)
    y=pd.to_numeric(base.totalRAPM,errors="coerce").to_numpy(float)
    n=pd.to_numeric(base.cleanPossessionExposure,errors="coerce").fillna(0).to_numpy(float)
    fit=(gp_old>=15)&(mpg_old>=12)&(n>=1000)&np.isfinite(y)
    if fit.sum()<600:raise RuntimeError("Insufficient prior season RAPM reference fit: "+str(fit.sum()))
    fitm=HuberRegressor(alpha=10,epsilon=1.5,max_iter=300).fit(now[fit].reshape(-1,1),y[fit])
    expected=fitm.intercept_+fitm.coef_[0]*now
    residual=np.clip(np.where(np.isfinite(y),y-expected,0),-7,7)
    cov=np.clip(divide(n,np.maximum(gp_old*mpg_old*1.95,1)),0,1)
    weight=.25*(n/(n+1200))*cov
    combined=now+np.clip(weight*residual,-1.75,1.75)
    # Context strata from historical ESPN opponent-adjusted standings:
    context=json.loads(Path("public/research_team_context.json").read_text())["teams"]["2025"]
    def context_rank(teamid):
        d=context.get(str(teamid),{})
        return float(d.get("rank",np.nan))
    oldrank=np.array([context_rank(i) for i in base.team_id_2025],float)
    ranknew=np.array([context_rank(i) for i in base.team_id_2026],float)
    transfer=base.team_id_2025.to_numpy(str)!=base.team_id_2026.to_numpy(str)
    masks={
       "allReturningRotation":eligible,
       "stayedSchool":eligible&~transfer,
       "allTransfers":eligible&transfer,
       "uptransferPriorTeamOutsideTop100":eligible&transfer&(oldrank>100)&(ranknew<=80),
       "weakOriginOutsideTop175":eligible&(oldrank>175),
       "highExposureRAPM":eligible&(n>=1000),
    }
    out={"status":"RESEARCH_ONLY_NOT_PREDICTIVE_APPROVAL","seasonSource":2025,"seasonTarget":2026,
         "label":"2026 estimated box-only BPM; NOT 2026 actual Torvik BPM",
         "rapmReferenceFitN":int(fit.sum()),"rapmReferenceSlope":float(fitm.coef_[0]),
         "rapmCoverageN":int(np.isfinite(y).sum()),
         "slices":{}}
    for name,mask in masks.items():
        if not mask.any():continue
        x=now[mask];z=combined[mask];g=target[mask]
        details={"n":int(mask.sum()),"matchedRAPM":int(np.sum(np.isfinite(y[mask])))}
        for k,score in (("boxOnly",x),("boxPlusRapm",z)):
            details[k]={"MAE":round(float(mean_absolute_error(g,score)),4),
              "Spearman":round(float(spearmanr(g,score).statistic),4),
              "bias":round(float(np.mean(score-g)),4)}
        details["deltaMAE_BoxMinusRapm"]=round(details["boxOnly"]["MAE"]-details["boxPlusRapm"]["MAE"],4)
        out["slices"][name]=details
    p=Path("research_qa/impact_v3_2025_to_2026_rapm_incremental.json")
    p.write_text(json.dumps(out,indent=2)+"\n")
    print(json.dumps(out,indent=2))
if __name__=="__main__":
    main()
