#!/usr/bin/env python3
"""Research only: distribute descriptive 2026 Impact V3 for all measured players.
Keep national-ranking eligibility as metadata, not a gate on player profile scores.
"""
import csv,json,subprocess,math
from pathlib import Path
root=Path("research_data/staged")
subprocess.run(["git","fetch","--depth=1","origin","impact-v3-nextseason-2025-rapm-validation"],check=True)
raw=subprocess.check_output(["git","show","FETCH_HEAD:research_qa/impact_v3_all_2026.csv"],text=True)
rows=list(csv.DictReader(raw.splitlines()))
records=[]
seen=set()
stats={"sourceRows":len(rows),"valid":0,"qualified":0,"limited":0,"invalid":0}
for row in rows:
    eid=str(row.get("athlete_id") or "").strip()
    try: impact=float(row.get("impactV3") or "nan")
    except ValueError:impact=float("nan")
    if not eid.isdigit() or eid in seen or not math.isfinite(impact) or abs(impact)>40:
        stats["invalid"]+=1
        continue
    seen.add(eid)
    qualified=str(row.get("impactRankEligible") or "").lower() in ("true","1","yes")
    records.append([eid,round(impact,3),int(qualified)])
    stats["valid"]+=1
    stats["qualified" if qualified else "limited"]+=1
assert len(rows)>=4800,stats
assert stats["valid"]>=3000,stats
assert stats["qualified"]>=2000,stats
out={"schemaVersion":2,"impactSeason":2026,"model":"Impact V3 historical descriptive impact","scope":"all available 2025-26 samples; ranking qualification separate","playerEntry":"[espnAthleteId,impactV3,rankingQualified]", "players":records}
(root/"impact_v3_2026_all_ready.json").write_text(json.dumps(out,separators=(",",":")))
print(json.dumps(stats))
