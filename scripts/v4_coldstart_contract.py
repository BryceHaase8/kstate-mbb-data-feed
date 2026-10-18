#!/usr/bin/env python3
"""Research-only 2027+ cold-start scoring contract.

Scoring uses ONLY first-party stored ESPN season box data and frozen
offline coefficient JSON. No network, hoopR, Torvik, SDV, or research RAPM.
When a new player has no minutes, output an unscored row, never an invented 0 BPM.
All shrinkage below is provisional, not yet predictive-validated for production.
"""
import argparse,json,sys
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent))
from impact_v3_research import bpm_proxy,features_from_espn

IDENTITY=("season","athlete_id")
def _num(df,key):
    return pd.to_numeric(df[key],errors="coerce").fillna(0)

def score_new_season(raw,coefficients,season,prior_ratings=None):
    if "season" not in raw.columns or "athlete_id" not in raw.columns:
        raise ValueError("season and ESPN athlete_id required")
    df=raw.loc[pd.to_numeric(raw["season"],errors="coerce")==season].copy()
    if df.empty:
        raise ValueError("No current-season ESPN players; refuse to publish")
    df["athlete_id"]=df["athlete_id"].fillna("").astype(str).str.strip()
    if df["athlete_id"].eq("").any() or df["athlete_id"].str.lower().eq("nan").any():
        raise ValueError("Missing ESPN athlete id; do not infer identity from name")
    if df["athlete_id"].duplicated().any():
        examples=df.loc[df.athlete_id.duplicated(keep=False),"athlete_id"].unique()[:5]
        raise ValueError("Duplicate athlete IDs within same season; upstream identity reconciliation required: "+repr(examples))
    if (_num(df,"gp")<0).any() or (_num(df,"mpg")<0).any():
        raise ValueError("Impossible season GP/minutes")
    df["minutes_observed"]=_num(df,"gp")*_num(df,"mpg")
    # No old ID whitelist. Every new ESPN athlete ID with season data is included.
    have=(df.minutes_observed>=40)&(_num(df,"gp")>=2)
    reliable=(df.minutes_observed>=300)&(_num(df,"gp")>=10)
    # Explicit no-data status protects 1000+ freshmen/internationals.
    df["rating_status"]=np.where(~have,"unscored",np.where(reliable,"established","provisional"))
    df["is_new_to_history"]=True
    if prior_ratings is not None:
        old=set(str(i) for i in prior_ratings)
        df["is_new_to_history"]=~df.athlete_id.isin(old)
    df["boxBPM_raw"]=np.nan
    df["boxBPM_shrunk"]=np.nan
    df["confidence_basis"]="no observed minutes"
    if have.any():
        # Restrict all scoring features to players with real on-court minutes.
        subset=df.loc[have]
        est=bpm_proxy(features_from_espn(subset),coefficients)
        n=subset.minutes_observed.to_numpy(float)
        new=subset.is_new_to_history.to_numpy(bool)
        # Conservative onboarding heuristic; optimize offline before production.
        strength=np.where(new,n/(n+300),n/(n+175))
        df.loc[have,"boxBPM_raw"]=est
        df.loc[have,"boxBPM_shrunk"]=est*strength
        df.loc[have,"confidence_basis"]=np.where(
            reliable[have],"observed 300+ minutes/10+ games",
            "provisional fewer than 300 minutes or 10 games"
        )
    # Rankings only after a documented sample threshold. No imaginary
    # RAPM for unseen players, no borrowed NCAA player ID.
    df["rankable"]=(df.rating_status=="established")
    df["rapm_used"]=False
    df["source"]="internal_ESPN_box_only"
    return df

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--player-stats",default="data/current_player_season_stats.csv")
    p.add_argument("--coefficients",default="research_qa/ebpm_v3_coefficients.json")
    p.add_argument("--season",type=int,required=True)
    p.add_argument("--out",default="research_qa/coldstart_research.csv")
    a=p.parse_args()
    raw=pd.read_csv(a.player_stats,dtype={"athlete_id":str},low_memory=False)
    params=json.loads(Path(a.coefficients).read_text())
    result=score_new_season(raw,params,a.season)
    Path(a.out).parent.mkdir(parents=True,exist_ok=True)
    result[["season","athlete_id","player_name","team_id","gp","mpg",
       "minutes_observed","rating_status","is_new_to_history","boxBPM_raw",
       "boxBPM_shrunk","rankable","rapm_used","source"]].to_csv(a.out,index=False)
    print(result.rating_status.value_counts().to_dict())
if __name__=="__main__":main()
