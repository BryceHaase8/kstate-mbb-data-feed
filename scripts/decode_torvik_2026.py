#!/usr/bin/env python3
"""Expand the supplied FINAL 2025-26 Torvik team-strength lookup for research.

Data source: user-supplied 2026_team_results.csv matched to 365 verified ESPN
team IDs in the earlier 2026 research archive. Efficiencies rounded to 0.01.
Never substitute the 2027 preseason feed for historical ratings.
"""
import base64,csv,io,zlib
from pathlib import Path
src=Path("research_qa/torvik_team_strength_2026.zlib.base64").read_text().strip()
raw=zlib.decompress(base64.b64decode(src+"="*((-len(src))%4))).decode()
rows=[]
for part in raw.split(";"):
    tid,oe,de=part.split(",")
    rows.append({"espnTeamId":tid,"adjOE":float(oe),"adjDE":float(de)})
ids=[r["espnTeamId"] for r in rows]
if len(rows)!=365 or len(set(ids))!=365:
    raise RuntimeError(f"Expected 365 unique ESPN IDs, got {len(rows)}")
ks=next((r for r in rows if r["espnTeamId"]=="2306"),None)
if not ks or not 75<ks["adjDE"]<135:
    raise RuntimeError("K-State ESPN crosswalk sanity check failed")
output=Path("research_qa/torvik_team_strength_2026.csv")
with output.open("w",newline="") as f:
    writer=csv.DictWriter(f,fieldnames=["espnTeamId","adjOE","adjDE"])
    writer.writeheader();writer.writerows(rows)
print("Verified historical Torvik 2026 rating rows:",len(rows),"K-State:",ks)
