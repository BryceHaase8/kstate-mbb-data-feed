#!/usr/bin/env python3
import urllib.request,pathlib,json,pandas as pd
url="https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_mens_college_basketball_shots/shots_2026.parquet"
path=pathlib.Path("/tmp/shot_2026.parquet")
if not path.exists():
    req=urllib.request.Request(url,headers={"User-Agent":"PortalResearch/1.0"})
    with urllib.request.urlopen(req,timeout=120) as r:path.write_bytes(r.read())
d=pd.read_parquet(path)
print("COUNTS",json.dumps({"rows":len(d),"columns":list(d.columns)}))
for col in ("coordinate_x","coordinate_y","coordinate_x_raw","coordinate_y_raw","type_text","score_value","scoring_play","team_id","athlete_id_1","athlete_id_2","season"):
    if col not in d.columns:continue
    x=d[col]
    if pd.api.types.is_numeric_dtype(x) and not pd.api.types.is_bool_dtype(x):
        print("METRIC",col,json.dumps({"nonnull":int(x.notna().sum()),"min":float(x.min()),"max":float(x.max()),"p01":float(x.quantile(.01)),"p50":float(x.quantile(.5)),"p99":float(x.quantile(.99))}))
    else:print("METRIC",col,json.dumps(x.value_counts(dropna=False).head(12).astype(int).to_dict(),default=str))
fields=["type_text","score_value","scoring_play","coordinate_x","coordinate_y","coordinate_x_raw","coordinate_y_raw","athlete_id_1","athlete_id_2","team_id","game_id"]
print("SAMPLE_ROWS",json.dumps(d[[f for f in fields if f in d.columns]].head(14).fillna("").astype(str).to_dict("records")))
