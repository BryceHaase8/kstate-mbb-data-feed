#!/usr/bin/env python3
"""Export full per-player 2025-26 RAPM V2 comparison for model-review only.

Uses completed minute-gated RAPM research variants and ESPN season player
directory; does NOT alter Portal/production, publish a recommended RAPM,
or train on future data.
"""
import csv,json
from pathlib import Path

SOURCE=Path("research_qa/rapm_v2_model_2026.json")
OUTPUT=Path("research_qa/rapm_v2_player_comparison_2026.csv")
EXPECTED=("baselineV1","torvikInformed","luckAdjusted","torvikAndLuckAdjusted")
m=json.loads(SOURCE.read_text())
assert m["season"]==2026 and m["status"]=="RESEARCH_ONLY_NOT_FOR_PORTAL"
assert m["gamesAccepted"]>=3500 and m["cleanPossessions"]>=390000
assert all(k in m["variants"] for k in EXPECTED)
variants={k:{str(r["espnAthleteId"]):r for r in m["variants"][k]} for k in EXPECTED}
ids=set(variants["baselineV1"])
assert len(ids)>=4000 and all(set(v)==ids for v in variants.values())

meta={}
with open("data/current_player_season_stats.csv",encoding="utf-8-sig",newline="") as f:
    for p in csv.DictReader(f):
        if str(p.get("season"))=="2026":
            meta[str(p.get("athlete_id"))]={
                "player_name":p.get("player_name",""),
                "team_name":p.get("team_name",""),
                "espnTeamId":p.get("team_id","")}

def val(v,pid,k):
    return v[pid][k]
fields=["espnAthleteId","player_name","team_name","espnTeamId",
        "verifiedCleanPossessionExposure",
        "v1_off","v1_def","v1_total",
        "torvik_off","torvik_def","torvik_total",
        "luck_off","luck_def","luck_total",
        "torvik_luck_off","torvik_luck_def","torvik_luck_total",
        "torvikOnlyChange","luckOnlyChange","bothChange",
        "above500Exposures","above1000Exposures"]
OUTPUT.parent.mkdir(parents=True,exist_ok=True)
with OUTPUT.open("w",encoding="utf-8",newline="") as f:
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
    for pid in sorted(ids,key=lambda k:(-int(val(variants["baselineV1"],k,"cleanPossessionExposure")),k)):
        b=variants["baselineV1"];t=variants["torvikInformed"];l=variants["luckAdjusted"];a=variants["torvikAndLuckAdjusted"]
        exposure=int(b[pid]["cleanPossessionExposure"])
        row={"espnAthleteId":pid,
            **meta.get(pid,{"player_name":"","team_name":"","espnTeamId":""}),
            "verifiedCleanPossessionExposure":exposure,
            "above500Exposures":int(exposure>=500),"above1000Exposures":int(exposure>=1000)}
        for label,v in (("v1",b),("torvik",t),("luck",l),("torvik_luck",a)):
            for side,key in (("off","offRAPM"),("def","defRAPM"),("total","totalRAPM")):
                row[label+"_"+side]=v[pid][key]
        row["torvikOnlyChange"]=round(t[pid]["totalRAPM"]-b[pid]["totalRAPM"],2)
        row["luckOnlyChange"]=round(l[pid]["totalRAPM"]-b[pid]["totalRAPM"],2)
        row["bothChange"]=round(a[pid]["totalRAPM"]-b[pid]["totalRAPM"],2)
        w.writerow(row)
print("Saved RAPM V2 per-player research comparison:",len(ids),"players",OUTPUT)
