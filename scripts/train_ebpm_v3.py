#!/usr/bin/env python3
"""Reproduce the box-only BPM proxy V3 using locally supplied player files.

Usage (source CSVs are kept off this public repository):
 python scripts/train_ebpm_v3.py --input-dir /path/to/torvik_csvs \
   --output /path/to/ebpm_v3_coefficients.json

Historical training seasons: 2022-2024 for hyperparameter selection on 2025;
2022-2025 for final fit. 2026 must remain completely untouched until evaluation.
This imitates Torvik BPM; it does NOT validate future transfer forecasting.
"""
import argparse,json
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.preprocessing import StandardScaler,PolynomialFeatures
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error,r2_score
from scipy.stats import spearmanr
from impact_v3_research import features_from_espn,FEATURES

def divide(a,b):
    a=np.asarray(a,dtype=float);b=np.asarray(b,dtype=float)
    return np.divide(a,b,out=np.zeros_like(a),where=b!=0)

def load_year(directory,year):
    path=directory/f"barttorvik_{year-1}_{str(year)[-2:]}_player_stats.csv"
    d=pd.read_csv(path)
    gp=d.GP.to_numpy(float);ast=d.ast.to_numpy(float)
    tov=divide(ast,d["ast/tov"].to_numpy(float))
    def val(col):return d[col].to_numpy(float)
    box=pd.DataFrame({
      "gp":gp,"mpg":val("mp"),"ppg":val("pts"),"rpg":val("treb"),
      "apg":ast,"spg":val("stl"),"bpg":val("blk"),"topg":tov,
      "two_pa_pg":divide(val("twoPA"),gp),
      "three_pa_pg":divide(val("TPA"),gp),
      "fta_pg":divide(val("FTA"),gp),
      "two_pm":val("twoPM"),"three_pm":val("TPM"),"ftm":val("FTM"),
      "two_pt_pct":divide(val("twoPM"),val("twoPA")),
      "three_pt_pct":divide(val("TPM"),val("TPA")),
      "ft_pct":divide(val("FTM"),val("FTA")),
      "efg_pct":val("eFG")/100,
      "ts_pct":val("TS_per")/100})
    x=features_from_espn(box)
    assert x.columns.tolist()==list(FEATURES)
    y=val("bpm")
    fitmask=(gp>=10)&(box.mpg>=7)&np.isfinite(y)&(y>=-25)&(y<=35)
    testmask=(gp>=20)&(box.mpg>=18)&np.isfinite(y)&(y>=-20)&(y<=35)
    weights=np.clip(np.sqrt(gp*box.mpg),7,40)
    return x,y,fitmask,testmask,weights

def eval_model(model,sc,poly,record):
    x,y,_,ok,_=record
    pred=model.predict(poly.transform(sc.transform(x)))
    a=y[ok];b=pred[ok]
    i=np.argsort(-a);j=np.argsort(-b)
    return {"players":int(ok.sum()),"mae":round(float(mean_absolute_error(a,b)),3),
      "r2":round(float(r2_score(a,b)),3),
      "spearman":round(float(spearmanr(a,b).statistic),3),
      "top100_overlap":len(set(i[:100])&set(j[:100])),
      "top50_overlap":len(set(i[:50])&set(j[:50]))}

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--input-dir",type=Path,required=True)
    a.add_argument("--output",type=Path,required=True)
    args=a.parse_args()
    records={year:load_year(args.input_dir,year) for year in range(2022,2027)}
    def fit(years,alpha):
        x=pd.concat([records[k][0].loc[records[k][2]] for k in years],ignore_index=True)
        y=np.concatenate([records[k][1][records[k][2]] for k in years])
        w=np.concatenate([records[k][4][records[k][2]] for k in years])
        sc=StandardScaler().fit(x)
        poly=PolynomialFeatures(2,include_bias=False)
        xp=poly.fit_transform(sc.transform(x))
        model=Ridge(alpha=alpha).fit(xp,y,sample_weight=w)
        return model,sc,poly
    candidates=[]
    for alpha in (200,600,1200,3000,6000):
        model,sc,poly=fit((2022,2023,2024),alpha)
        candidates.append((eval_model(model,sc,poly,records[2025])["mae"],alpha))
    alpha=min(candidates)[1]
    model,sc,poly=fit((2022,2023,2024,2025),alpha)
    holdout=eval_model(model,sc,poly,records[2026])
    obj={"features":list(FEATURES),"means":np.round(sc.mean_,7).tolist(),
      "scales":np.round(sc.scale_,7).tolist(),
      "coefficients":np.round(model.coef_,7).tolist(),
      "intercept":round(float(model.intercept_),7),
      "trainingYears":[2022,2023,2024,2025],
      "holdout2026":holdout,
      "targetNote":"Retrospective historical Torvik BPM proxy; not next-season predictive validity."}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(obj,indent=2)+"\n")
    print("Selected ridge alpha",alpha,"held-out 2026",holdout)
if __name__=="__main__":
    main()
