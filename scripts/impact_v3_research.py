#!/usr/bin/env python3
"""Research-only 2025-26 Composite Impact V3. Never publishes to Portal/main.

Inputs: ESPN box-score season data, saved V2 player RAPM comparison,
and a box-only BPM proxy fitted on 2022-25 historical player data.
The raw RAPM variant used is luck-only. There is NO Torvik team offset.
"""
from __future__ import annotations
import argparse
import json
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.linear_model import HuberRegressor

FEATURES = ("mpg","gp_sqrt","ppg30","rpg30","apg30","spg30","bpg30",
    "topg30","two_pa30","three_pa30","fta30","two_pct","three_pct",
    "ft_pct","efg_pct","ts_pct","three_m30","ftm30","two_m30","ast_to_clip")

def divide(a,b):
    a=np.asarray(a,dtype=float); b=np.asarray(b,dtype=float)
    return np.divide(a,b,out=np.zeros_like(a),where=b!=0)

def features_from_espn(raw):
    # All features must exist in the self-contained hoopR/ESPN daily feed.
    required={"gp","mpg","ppg","rpg","apg","spg","bpg","topg",
      "two_pa_pg","three_pa_pg","fta_pg","two_pm","three_pm","ftm",
      "two_pt_pct","three_pt_pct","ft_pct","efg_pct","ts_pct"}
    missing=sorted(required-set(raw.columns))
    if missing: raise ValueError("Required ESPN fields missing: "+str(missing))
    def get(key):
        return pd.to_numeric(raw[key],errors="coerce").fillna(0).to_numpy(float)
    gp=get("gp"); mpg=get("mpg"); ppg=get("ppg")
    scale=30/np.maximum(mpg,2.0)
    def pct(key):
        x=get(key)
        return np.where(x>1.001,x/100,x)
    apg=get("apg"); tov=get("topg")
    vals={
      "mpg":np.clip(mpg,0,42),
      "gp_sqrt":np.sqrt(np.clip(gp,0,45)),
      "ppg30":np.clip(ppg*scale,0,55),
      "rpg30":np.clip(get("rpg")*scale,0,26),
      "apg30":np.clip(apg*scale,0,20),
      "spg30":np.clip(get("spg")*scale,0,9),
      "bpg30":np.clip(get("bpg")*scale,0,10),
      "topg30":np.clip(tov*scale,0,15),
      "two_pa30":np.clip(get("two_pa_pg")*scale,0,35),
      "three_pa30":np.clip(get("three_pa_pg")*scale,0,30),
      "fta30":np.clip(get("fta_pg")*scale,0,30),
      "two_pct":np.clip(pct("two_pt_pct"),0,1),
      "three_pct":np.clip(pct("three_pt_pct"),0,1),
      "ft_pct":np.clip(pct("ft_pct"),0,1),
      "efg_pct":np.clip(pct("efg_pct"),0,1.5),
      "ts_pct":np.clip(pct("ts_pct"),0,1.2),
      "three_m30":np.clip(divide(get("three_pm"),gp)*scale,0,12),
      "ftm30":np.clip(divide(get("ftm"),gp)*scale,0,20),
      "two_m30":np.clip(divide(get("two_pm"),gp)*scale,0,25),
      "ast_to_clip":np.clip(divide(apg,tov),0,8),
    }
    return pd.DataFrame({k: vals[k] for k in FEATURES},index=raw.index)

def bpm_proxy(matrix,params):
    assert params["features"]==list(FEATURES)
    mu=np.asarray(params["means"],float); sd=np.asarray(params["scales"],float)
    b=np.asarray(params["coefficients"],float)
    x=(matrix[list(FEATURES)].to_numpy(float)-mu)/sd
    assert np.isfinite(x).all(), "Invalid BPM inputs"
    n=x.shape[1]; assert len(b)==n+n*(n+1)//2, (len(b),n)
    score=np.full(len(x),float(params["intercept"]))+x@b[:n]
    offset=n
    # Matches sklearn PolynomialFeatures(degree=2,include_bias=False) order:
    # x1,x2,...,xN,x1^2,x1*x2,...,xN^2.
    for i in range(n):
        for j in range(i,n):
            score+=b[offset]*x[:,i]*x[:,j]
            offset+=1
    assert offset==len(b)
    return np.clip(score,-20,22)

def build(args):
    params=json.loads(Path(args.coefficients).read_text())
    allstats=pd.read_csv(args.player_stats,dtype={"athlete_id":str,"team_id":str},low_memory=False)
    allstats["season"]=pd.to_numeric(allstats.season,errors="coerce")
    stats=allstats.loc[allstats.season==args.season].copy()
    if len(stats)<4000: raise ValueError("Unexpectedly small season player pool "+str(len(stats)))
    stats["athlete_id"]=stats["athlete_id"].astype(str)
    stats["minutes_total"]=pd.to_numeric(stats["gp"],errors="coerce").fillna(0)*pd.to_numeric(stats["mpg"],errors="coerce").fillna(0)
    stats=stats.sort_values("minutes_total",ascending=False).drop_duplicates("athlete_id").reset_index(drop=True)
    stats["estimatedBPM"]=bpm_proxy(features_from_espn(stats),params)
    rapm=pd.read_csv(args.rapm_comparison,dtype={"espnAthleteId":str},low_memory=False)
    required={"espnAthleteId","v1_total","luck_total","torvik_luck_total","verifiedCleanPossessionExposure"}
    assert required.issubset(rapm.columns)
    assert rapm.espnAthleteId.is_unique
    needed=["espnAthleteId","v1_total","luck_total","torvik_luck_total","verifiedCleanPossessionExposure"]
    stats=stats.merge(rapm[needed],left_on="athlete_id",right_on="espnAthleteId",how="left",validate="one_to_one")
    stats["verifiedCleanPossessionExposure"]=pd.to_numeric(stats["verifiedCleanPossessionExposure"],errors="coerce").fillna(0)
    for col in ("luck_total","v1_total","torvik_luck_total"):
        stats[col]=pd.to_numeric(stats[col],errors="coerce")
    gp=pd.to_numeric(stats.gp,errors="coerce").fillna(0).to_numpy(float)
    mpg=pd.to_numeric(stats.mpg,errors="coerce").fillna(0).to_numpy(float)
    n=stats["verifiedCleanPossessionExposure"].to_numpy(float)
    y=stats.luck_total.to_numpy(float)
    base=stats.estimatedBPM.to_numpy(float)
    # Fit a reference relationship on well-exposed players to put RAPM on
    # a common baseline scale. Use RAPM only as a residual correction.
    good=(n>=1000)&(gp>=15)&(mpg>=12)&np.isfinite(y)&np.isfinite(base)
    if good.sum()<800:raise ValueError(f"Insufficient high-exposure sample: {good.sum()}")
    model=HuberRegressor(epsilon=1.5,alpha=10,max_iter=300).fit(base[good].reshape(-1,1),y[good])
    slope=float(model.coef_[0]); intercept=float(model.intercept_)
    if not (0.10<slope<2.0):
        raise ValueError("BPM->RAPM scale coefficient unexpectedly unstable: "+str(slope))
    expected=intercept+slope*base
    residual=np.where(np.isfinite(y),y-expected,0)
    residual=np.clip(residual,-7,7)
    # Verified exposure accounts for observed games; coverage estimates
    # player-specific verified on-court possessions versus plausible minutes.
    # 1.95 total team possessions/min is deliberately only an approximation.
    coverage=np.clip(divide(n,np.maximum(gp*mpg*1.95,1)),0,1)
    reliability=np.clip(n/(n+1200),0,1)*coverage
    weight=.25*reliability
    impact=np.clip(weight*residual,-1.75,1.75)
    stats["expectedLuckRAPM"]=np.where(np.isfinite(y),expected,np.nan)
    stats["rapmResidual"]=np.where(np.isfinite(y),residual,np.nan)
    stats["estimatedVerifiedCoverage"]=coverage
    stats["rapmWeight"]=weight
    stats["rapmContribution"]=impact
    stats["impactV3"]=base+impact
    stats["impactRankEligible"]=(gp>=20)&(mpg>=18)
    # All eligible players are ranked, whether or not they have RAPM.
    stats["rank"]=np.nan
    eligible=stats[stats.impactRankEligible].sort_values("impactV3",ascending=False)
    stats.loc[eligible.index,"rank"]=np.arange(1,len(eligible)+1)
    cols=["rank","athlete_id","player_name","team_name","team_id","gp","mpg","ppg","rpg","apg",
      "estimatedBPM","v1_total","luck_total","torvik_luck_total",
      "verifiedCleanPossessionExposure","estimatedVerifiedCoverage","rapmWeight","rapmResidual",
      "rapmContribution","impactV3","impactRankEligible"]
    def save(x,path):
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        x[cols].to_csv(path,index=False,float_format="%.4f")
    save(stats.sort_values("impactV3",ascending=False),args.output)
    save(eligible.head(100),args.top100)
    summary={
      "model":"RESEARCH_ONLY_V3_NOT_FOR_PORTAL",
      "season":args.season,
      "playerPool":len(stats),
      "eligiblePlayers":int(stats.impactRankEligible.sum()),
      "playersWithLuckRAPM":int(np.isfinite(y).sum()),
      "highExposureFitPlayers":int(good.sum()),
      "rapmReferenceIntercept":round(intercept,5),
      "rapmReferenceSlope":round(slope,5),
      "medianAbsRapmContribution":round(float(np.median(abs(impact))),4),
      "p95AbsRapmContribution":round(float(np.quantile(abs(impact),.95)),4),
      "maxAbsRapmContribution":round(float(max(abs(impact))),4),
      "top100LowExposure":int((eligible.head(100).verifiedCleanPossessionExposure<500).sum()),
      "top100Head":[{"name":r.player_name,"school":r.team_name,"impact":round(float(r.impactV3),2),
        "bpm":round(float(r.estimatedBPM),2),"rapm":None if pd.isna(r.luck_total) else round(float(r.luck_total),2)}
        for r in eligible.head(30).itertuples()],
      "warnings":[
         "Box-only BPM is calibrated against historical Torvik BPM: this is metric-reproduction validation, NOT predictive recruiting validation.",
         "Luck RAPM uses 2025-26 other-games shooter rates; must switch to strictly past-games priors for live updates.",
         "RAPM V2 official-minute sample has about 57 percent coverage; estimated individual coverage is heuristic.",
         "No Torvik team-strength offset. Team/individual impact identification remains a research issue.",
         "RAPM residual weight is provisional, not optimized on future season outcomes.",
         "Do not merge into main or publish to Portal."
      ]
    }
    Path(args.report).write_text(json.dumps(summary,indent=2)+"\n")
    print("V3 IMPACT RESEARCH",json.dumps({k:v for k,v in summary.items() if k!="top100Head" and k!="warnings"}))
    print("TOP 30\n",eligible[["player_name","team_name","impactV3","estimatedBPM","luck_total","rapmContribution"]].head(30).to_string(index=False))

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--season",type=int,default=2026)
    p.add_argument("--coefficients",default="research_qa/ebpm_v3_coefficients.json")
    p.add_argument("--player-stats",default="data/current_player_season_stats.csv")
    p.add_argument("--rapm-comparison",default="research_qa/rapm_v2_player_comparison_2026.csv")
    p.add_argument("--output",default="research_qa/impact_v3_all_2026.csv")
    p.add_argument("--top100",default="research_qa/impact_v3_top_100_2026.csv")
    p.add_argument("--report",default="research_qa/impact_v3_audit_2026.json")
    build(p.parse_args())
