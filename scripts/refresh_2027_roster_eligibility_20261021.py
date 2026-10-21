#!/usr/bin/env python3
"""Research-only: build 2027 ESPN roster + eligibility browser assets, ID-first."""
import argparse,csv,gzip,json,collections,datetime
from pathlib import Path
R=Path("research_data/staged");QA=Path("research_qa/roster_integration");QA.mkdir(parents=True,exist_ok=True)
parser=argparse.ArgumentParser();parser.add_argument("--pre",action="store_true");parser.add_argument("--final",action="store_true")
args=parser.parse_args();assert args.pre != args.final
source=json.loads((R/"current_roster_2027_candidate.json").read_text());people=source["players"]
assert source["rosterSeason"]==2027 and source["totalTeams"]==365 and 5400<=len(people)<=6000,len(people)
ids=[str(p.get("espnAthleteId") or "") for p in people]
assert len(ids)==len(set(ids)) and all(x.isdigit() for x in ids)
teamids=set(str(p["teamId"]) for p in people);assert len(teamids)==365
auditfile=Path("/tmp/espn_roster_ids_20261021.csv");assert auditfile.exists(),"Independent roster audit missing"
with auditfile.open() as f:reference={(str(r["team_id"]),str(r["athlete_id"])) for r in csv.DictReader(f) if str(r["season"])=="2027"}
member={(str(p["teamId"]),str(p["espnAthleteId"])) for p in people}
missing=reference-member;unexpected=member-reference
assert len(reference)==5541 and len(missing)<=10 and len(unexpected)<=10,(len(member),len(missing),len(unexpected))
first={}
with gzip.open(R/"player_seasons_2020_2026.csv.gz","rt") as f:
    for v in csv.DictReader(f):
        pid=str(v.get("athlete_id") or "")
        try:year=int(v.get("season") or 0)
        except ValueError:continue
        if pid.isdigit() and 2020<=year<=2026:first[pid]=min(first.get(pid,year),year)
classes={}
if args.final:
    c=json.loads((R/"roster_2027_class_evidence.json").read_text())
    assert c["rosterSeason"]==2027
    for pid,fields in c.get("players",{}).items():
        if isinstance(fields,list) and len(fields)>=2:classes[str(pid)]=(str(fields[0]),str(fields[1]))
    matched=sum(1 for p in people if str(p["espnAthleteId"]) in classes and classes[str(p["espnAthleteId"])][1]==str(p["teamId"]))
    assert matched>=int(len(people)*.90),(matched,len(people))
else:matched=0
# Preserve the site's existing FR=4, SO=3, JR=2, SR=1 planning convention,
# but don't force ANY athlete with previous games to 0. Staff override wins.
class_years={"FR":4,"SO":3,"JR":2,"SR":1,"GR":0,"5TH":0,"RS-FR":3,"RS-SO":2,"RS-JR":1,"RS-SR":0}
counts=collections.Counter();methods=collections.Counter()
for p in people:
    pid=str(p["espnAthleteId"]);tid=str(p["teamId"]);cls,ctid=classes.get(pid,("",""))
    old=first.get(pid)
    if cls in class_years and ctid==tid:
        years=class_years[cls];basis="ESPN_2027_ROSTER_CLASS_"+cls;methods["class"]+=1
    elif old is not None:
        years=max(0,min(4,4-(2027-old)));basis="EARLIEST_DI_BOX_SEASON_PROXY";methods["first_seen_fallback"]+=1
    else:
        years=4;basis="NO_CLASS_OR_DI_HISTORY_PROVISIONAL";methods["no_evidence_fallback"]+=1
    p.update(eligibilityEstimate=years,eligibilityTargetSeason="2027-28",eligibilityEstimateBasis=basis,eligibilityConfidence="PROVISIONAL_STAFF_EDITABLE")
    counts[years]+=1
(R/"current_roster_2027_candidate.json").write_text(json.dumps(source,separators=(",",":"),ensure_ascii=False))
with (R/"current_roster_2027_identity.csv").open(newline="") as f:identity=list(csv.DictReader(f))
assert {r["athlete_id"] for r in identity}==set(ids)
cols=list(identity[0].keys())+["eligibility_estimate","eligibility_basis","eligibility_target","class2027"]
byid={str(p["espnAthleteId"]):p for p in people}
with (R/"current_roster_2027_identity_estimated.csv").open("w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=cols);w.writeheader()
    for row in identity:
        p=byid[row["athlete_id"]];cl,tid=classes.get(row["athlete_id"],("",""))
        row.update(eligibility_estimate=p["eligibilityEstimate"],eligibility_basis=p["eligibilityEstimateBasis"],eligibility_target="2027-28",class2027=cl if tid==row["team_id"] else "")
        w.writerow(row)
keys=("espnAthleteId","name","team","teamId","position","height","weight","headshot","birthPlace","eligibilityEstimate","eligibilityTargetSeason","identityStatus")
flat=[{k:p[k] for k in keys if k in p} for p in people]
zero=[p for p in people if p["eligibilityEstimate"]==0]
for filename,part in [("roster_2027_site_compact.json",flat),("roster_2027_zero_fallback.json",[{k:p[k] for k in keys if k in p} for p in zero])]:
    (R/filename).write_text(json.dumps({"schemaVersion":1,"rosterSeason":2027,"totalTeams":365,"players":part},separators=(",",":"),ensure_ascii=False))
teams={str(p["teamId"]):p["team"] for p in people};assert len(teams)==365
rows=[]
for p in people:
    code=0 if p.get("teamReadiness")=="UPDATED_NEEDS_FINAL_COMPLETENESS_QA" else 1
    if p.get("identityStatus")!="ESPN_ID_WITH_BIO":code=2
    rows.append([str(p["espnAthleteId"]),str(p["name"]),str(p["teamId"]),p.get("position") or "",p.get("height") or "",p.get("weight") or "",p["eligibilityEstimate"],p.get("birthPlace") or "",code])
header={"schemaVersion":3,"rosterSeason":2027,"totalTeams":365,"eligibilityTargetSeason":"2027-28","teams":teams}
for fn,part in [("roster_2027_fast_ready.json",rows),("roster_2027_zero_fast_ready.json",[p for p in rows if p[6]==0])]:
    (R/fn).write_text(json.dumps(dict(header,players=part),separators=(",",":"),ensure_ascii=False))
(R/"roster_2027_site_compact_ready.json").write_bytes((R/"roster_2027_site_compact.json").read_bytes())
(R/"roster_2027_zero_fallback_ready.json").write_bytes((R/"roster_2027_zero_fallback.json").read_bytes())
qa={"auditDate":datetime.date.today().isoformat(),"stage":"final" if args.final else "pre-class","rosterMembers":len(people),"uniqueIds":len(ids),"teams":len(teams),"classified":matched,"auditOct21Memberships":len(reference),"missingFromStage":len(missing),"newSinceAudit":len(unexpected),"methodCounts":dict(methods),"eligibilityCounts":{str(i):counts[i] for i in range(5)},"staffOverridesRemainAuthoritative":True,"officialEligibilityCertification":False,"nilImpactStaffSheetsUntouched":True}
(QA/"roster_2027_refreshed_class_estimates_qa.json").write_text(json.dumps(qa,indent=2))
print(json.dumps(qa))
