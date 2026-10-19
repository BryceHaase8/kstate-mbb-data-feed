#!/usr/bin/env python3
"""Produce compact safe public research assets; independent from live Portal."""
import csv, json, subprocess, gzip
from pathlib import Path
root=Path("research_data/staged")
roster=json.loads((root/"current_roster_2027_candidate.json").read_text())
all_players=roster["players"]

# Re-derive estimates every time. ESPN roster refreshes can overwrite the
# previously staged values; failure must not hide zero-year athletes.
first_seen={}
with gzip.open(root/"player_seasons_2020_2026.csv.gz","rt",encoding="utf-8") as f:
    for row in csv.DictReader(f):
        pid=str(row.get("athlete_id") or "").strip()
        try: year=int(row.get("season") or 0)
        except ValueError: continue
        if pid.isdigit() and 2020<=year<=2026:
            first_seen[pid]=min(first_seen.get(pid,year),year)
for p in all_players:
    pid=str(p.get("espnAthleteId") or "")
    assert pid.isdigit() and p.get("name") and p.get("teamId") and p.get("team")
    first=first_seen.get(pid)
    p["eligibilityEstimate"]=max(0,min(4,4-(2027-first))) if first is not None else 4
    p["eligibilityTargetSeason"]="2027-28"
    p["eligibilityEstimateBasis"]="FIRST_OBSERVED_DI_BOX_SEASON_PROXY" if first is not None else "NO_DIVISION_I_STATS_FRESHMAN_PROXY"
# These remain low-confidence five-year planning proxies, not official NCAA
# age/enrollment determinations. Staff overrides always take precedence.

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

# Keep the website's preferred v3 compact sources synchronized, not merely the
# larger fallback files. This fixes the previous silent zero-year disappearance.
teams={}
small=[]
for p in all_players:
    tid=str(p["teamId"])
    if tid in teams: assert teams[tid]==p["team"]
    teams[tid]=p["team"]
    review=0 if p.get("teamReadiness")=="UPDATED_NEEDS_FINAL_COMPLETENESS_QA" else 1
    if p.get("identityStatus")!="ESPN_ID_WITH_BIO":review=2
    small.append([str(p["espnAthleteId"]),str(p["name"]),tid,p.get("position") or "",p.get("height") or "",p.get("weight") or "",p["eligibilityEstimate"],p.get("birthPlace") or "",review])
assert len(teams)>=350 and len({r[0] for r in small})==len(small)
head={"schemaVersion":3,"rosterSeason":2027,"totalTeams":len(teams),"eligibilityTargetSeason":"2027-28","teams":teams}
(root/"roster_2027_fast_ready.json").write_text(json.dumps(dict(head,players=small),separators=(",",":"),ensure_ascii=False))
(root/"roster_2027_zero_fast_ready.json").write_text(json.dumps(dict(head,players=[r for r in small if r[6]==0]),separators=(",",":"),ensure_ascii=False))
(root/"roster_2027_site_compact_ready.json").write_text((root/"roster_2027_site_compact.json").read_text())
(root/"roster_2027_zero_fallback_ready.json").write_text((root/"roster_2027_zero_fallback.json").read_text())

print(json.dumps({"roster":len(all_players),"zero":len(zero),"impact":len(entries),"compressedRosterBytes":(root/"roster_2027_site_compact.json").stat().st_size,"zeroBytes":(root/"roster_2027_zero_fallback.json").stat().st_size,"impactBytes":(root/"impact_v3_2026_site.json").stat().st_size}))
