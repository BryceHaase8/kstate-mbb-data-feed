#!/usr/bin/env python3
"""Manual, archive-only NCAA league-wide RAPM incremental backtest.

External 2023/24/25 RAPM CSV.GZ files may be downloaded by a MANUAL RESEARCH
workflow. They never appear in main, in model inference, or daily ingestion.
Freeze features at source season; train 2023/24 -> 2024/25, hold out
2025 -> 2026. ID joining is fail-closed, not fuzzy.
Target: ESPN-based proxy for NEXT-year BPM; NOT Torvik ground truth.
"""
import argparse,collections,json,re,sys,unicodedata
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import mean_absolute_error
from scipy.stats import spearmanr
sys.path.insert(0,"scripts")
from impact_v3_research import bpm_proxy,features_from_espn

def norm(s):
    s=unicodedata.normalize("NFKD",str(s)).lower()
    s="".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]","",s)

def ncaaplayer_name(s):
    s=str(s)
    if "." in s:
        last,first=s.split(".",1)
        return norm(first+last)
    if "," in s:
        last,first=s.split(",",1)
        return norm(first+last)
    return norm(s)

def team_agrees(a,b):
    a,b=norm(a),norm(b)
    if not a or not b:return False
    # Whole short conference ambiguous aliases are never force-matched.
    return a==b or (len(a)>=5 and b.startswith(a)) or (len(b)>=5 and a.startswith(b))

def _numeric(s):
    return pd.to_numeric(s,errors="coerce").fillna(0)

def match_ncaa_to_espn(src, archive):
    # Name must be unique WITHIN each season in both sources and current
    # school string must agree; non-unique/mismatched cases remain unmatched.
    src=src.copy()
    src["key"]=src.player_name.map(norm)
    a=archive.copy()
    if not {"player","team","rapm_net","off_poss","def_poss"}.issubset(a.columns):
        raise ValueError("Unexpected external league-wide RAPM schema")
    a["key"]=a.player.map(ncaaplayer_name)
    a["rapm_net"]=pd.to_numeric(a.rapm_net,errors="coerce")
    a["exposure"]=pd.to_numeric(a.off_poss,errors="coerce").fillna(0)+pd.to_numeric(a.def_poss,errors="coerce").fillna(0)
    a=a[a.rapm_net.notna() & (a.exposure>0)].copy()
    e_unique=src.key.value_counts();n_unique=a.key.value_counts()
    src=src[src.key.map(e_unique).eq(1)]
    a=a[a.key.map(n_unique).eq(1)]
    m=src.merge(a[["key","team","rapm_net","exposure"]],on="key",how="left",validate="one_to_one",suffixes=("","_ncaa"))
    agree=np.array([team_agrees(t1,t2) for t1,t2 in zip(m.team_name,m.team)],bool)
    m["matchedRapm"]=m.rapm_net.notna() & agree
    m.loc[~m.matchedRapm,["rapm_net","exposure"]]=np.nan
    return m,{"sourceESPN":int(len(src)),"externalRows":int(len(archive)),
       "uniqueNameMatchesAndSchoolVerified":int(m.matchedRapm.sum()),
       "uniqueNameMatchButSchoolMismatch":int((m.rapm_net.isna() & ~m.matchedRapm).sum())}

def teamrank(context,season,ids):
    yy=context.get(str(season),{})
    return np.array([float(yy.get(str(x),{}).get("rank",180) or 180) for x in ids])

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--input-dir",type=Path,required=True)
    a.add_argument("--player-stats",default="data/current_player_season_stats.csv")
    a.add_argument("--coefficients",default="research_qa/ebpm_v3_coefficients.json")
    a.add_argument("--team-context",default="public/research_team_context.json")
    a.add_argument("--report",default="research_qa/v4_archive_rapm_predictiveness.json")
    args=a.parse_args()
    params=json.loads(Path(args.coefficients).read_text())
    raw=pd.read_csv(args.player_stats,dtype={"athlete_id":str,"team_id":str},low_memory=False)
    raw["season"]=pd.to_numeric(raw.season,errors="coerce")
    context=json.loads(Path(args.team_context).read_text())["teams"]
    years={}
    for season in (2023,2024,2025,2026):
        x=raw[raw.season==season].copy()
        if len(x)<4000:raise RuntimeError(f"Missing/low ESPN year {season}: {len(x)}")
        x["estBPM"]=bpm_proxy(features_from_espn(x),params)
        x=x.sort_values("minutes",ascending=False).drop_duplicates("athlete_id")
        years[season]=x
    cohorts=[];audit={}
    for source in (2023,2024,2025):
        path=args.input_dir/f"ncaa_mbb_rapm_{source}.csv.gz"
        archive=pd.read_csv(path,dtype={"player_id":str,"person_id":str},compression="gzip",low_memory=False)
        # Fail closed: these data must be NATIONAL rather than within-team RAPM.
        if "estimand" not in archive.columns or not archive.estimand.astype(str).str.contains("league",case=False).all():
            raise ValueError(f"{source}: archive is not demonstrably league-wide")
        player,a=match_ncaa_to_espn(years[source],archive)
        nxt=years[source+1][["athlete_id","team_id","gp","mpg","estBPM"]].rename(columns=
          {"team_id":"destination_team_id","gp":"gp_next","mpg":"mpg_next","estBPM":"outcome"})
        player=player.merge(nxt,on="athlete_id",how="inner",validate="one_to_one")
        g=_numeric(player.gp);m=_numeric(player.mpg)
        mask=(g>=10)&(m>=10)&(_numeric(player.gp_next)>=10)&(_numeric(player.mpg_next)>=10)
        player=player.loc[mask & player.matchedRapm].copy()
        player["originRank"]=teamrank(context,source,player.team_id)
        player["destPriorRank"]=teamrank(context,source,player.destination_team_id)
        player["changedSchool"]=(player.team_id!=player.destination_team_id).astype(int)
        player["rapm_net"]=pd.to_numeric(player.rapm_net,errors="coerce")
        player["logExposure"]=np.log1p(player.exposure.clip(lower=0))
        player["year"]=source
        cohorts.append(player)
        a["returnersMatchedAndEligible"]=int(len(player))
        audit[source]=a
    x=pd.concat(cohorts,ignore_index=True)
    train=x[x.year.isin([2023,2024])];test=x[x.year==2025]
    if len(train)<550 or len(test)<250:
        report={"status":"INSUFFICIENT_ARCHIVE_CROSSWALK_COVERAGE","byYear":audit,
          "trainCount":len(train),"testCount":len(test),
          "notice":"No predictive claim; identity join too sparse. Add explicit NCAA-ESPN ID bridge rather than fuzzy matching."}
    else:
        basecols=["estBPM","gp","mpg","ppg","rpg","apg","spg","bpg","topg",
                  "three_pa_pg","three_pt_pct","originRank","destPriorRank","changedSchool"]
        extra=["rapm_net","logExposure"]
        def features(df,columns):
            return df[columns].apply(pd.to_numeric,errors="coerce").fillna(0).to_numpy(float)
        scores={}
        for name,cols in (("boxContext",basecols),("boxContextPlusArchivedRAPM",basecols+extra)):
            model=make_pipeline(StandardScaler(),Ridge(alpha=100.0))
            model.fit(features(train,cols),train.outcome.to_numpy(float))
            scores[name]=model.predict(features(test,cols))
        true=test.outcome.to_numpy(float);p0=scores["boxContext"];p1=scores["boxContextPlusArchivedRAPM"]
        absdiff=np.abs(true-p0)-np.abs(true-p1)
        rng=np.random.default_rng(1618)
        means=np.array([absdiff[rng.integers(0,len(absdiff),len(absdiff))].mean() for _ in range(1000)])
        report={"status":"RESEARCH_BACKTEST_COMPLETED_NOT_PRODUCTION",
          "estimand":"league-wide archived NCAA RAPM; source-season only",
          "sourceYears":[2023,2024,2025],"targetHoldoutSeason":2026,
          "target":"2026 ESPN derived box BPM proxy, not 2026 independent Torvik BPM",
          "matches":audit,"trainCount":int(len(train)),"testCount":int(len(test)),
          "model":"StandardScaler + Ridge(alpha=100) trained 2023->24 and 2024->25",
          "baselineMAE":round(float(mean_absolute_error(true,p0)),4),
          "withArchiveRapmMAE":round(float(mean_absolute_error(true,p1)),4),
          "deltaMAE_positive_means_RAPM_helped":round(float(absdiff.mean()),4),
          "deltaMAE_bootstrap95":[round(float(z),4) for z in np.quantile(means,[.025,.975])],
          "baselineSpearman":round(float(spearmanr(true,p0).statistic),4),
          "withRapmSpearman":round(float(spearmanr(true,p1).statistic),4),
          "warnings":["Only rotation survivors included; no roster survival test.",
                      "External RAPM is an offline historical benchmark, never used in the live model.",
                      "Team aliases must agree; unmatched identities excluded.",
                      "One-season holdout is directional; repeat across other years and independent labels."]}
    Path(args.report).parent.mkdir(parents=True,exist_ok=True)
    Path(args.report).write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))
if __name__=="__main__":main()
