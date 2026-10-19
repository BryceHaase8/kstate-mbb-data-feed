#!/usr/bin/env python3
"""Produce compact safe public research assets; independent from live Portal."""
import csv, json, subprocess
from pathlib import Path
root=Path("research_data/staged")
roster=json.loads((root/"current_roster_2027_candidate.json").read_text())
all_players=roster["players"]
assert len(all_players)>=5400
zero=[p for p in all_players if p.get("eligibilityEstimate")==0]
assert len(zero)>=350
keep=("espnAthleteId","name","team","teamId","position","height","weight","headshot","birthPlace","eligibilityEstimate","eligibilityTargetSeason","identityStatus")
minify=lambda p:{k:p[k] for k in keep if k in p}
(root/"roster_2027_site_compact.json").write_text(json.dumps({"schemaVersion":1,"rosterSeason":2027,"totalTeams":365,"players":[minify(p) for p in all_players]},separators=(",",":"),ensure_ascii=False))
(root/"roster_2027_zero_fallback.json").write_text(json.dumps({"schemaVersion":1,"rosterSeason":2027,"totalTeams":365,"players":[minify(p) for p in zero]},separators=(",",":"),ensure_ascii=False))
# Base64 blob not needed; fetch V3 archive from an isolated historical research branch, not hoopR RAPM.
subprocess.run(["git","fetch","--depth=1","origin","impact-v3-nextseason-2025-rapm-validation"],check=True,stdout=subprocess.DEVNULL)
csvtext=subprocess.check_output(["git","show","FETCH_HEAD:research_qa/impact_v3_all_2026.csv"],text=True)
src=list(csv.DictReader(csvtext.splitlines()))
entries=[]
for r in src:
    if r["impactRankEligible"]=="True":
        athlete_id=r["athlete_id"].strip()
        value=float(r["impactV3"])
        if athlete_id.isdigit() and -25<value<25:
            entries.append([athlete_id,round(value,3)])
assert len(entries)>2000
(root/"impact_v3_2026_site.json").write_text(json.dumps({"schemaVersion":1,"impactSeason":2026,"model":"Impact V3 historical descriptive impact","rankEligibleOnly":True,"players":entries},separators=(",",":")))
print(json.dumps({"roster":len(all_players),"zero":len(zero),"impact":len(entries),"compressedRosterBytes":(root/"roster_2027_site_compact.json").stat().st_size,"zeroBytes":(root/"roster_2027_zero_fallback.json").stat().st_size,"impactBytes":(root/"impact_v3_2026_site.json").stat().st_size}))
