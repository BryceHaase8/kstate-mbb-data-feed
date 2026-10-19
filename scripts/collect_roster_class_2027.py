#!/usr/bin/env python3
"""Research only: ESPN class evidence for verified 2026-27 roster IDs.
No player may be added or reassigned by this collector. Does not overwrite staff.
"""
import json,urllib.request,time,re,concurrent.futures
from pathlib import Path
root=Path("research_data/staged")
roster=json.loads((root/"roster_2027_fast_ready.json").read_text())
members={str(p[0]):str(p[2]) for p in roster["players"]}
team_ids=sorted(roster["teams"],key=int)
def clean(value):
    s=str(value or "").strip().lower().replace(".","")
    for token,label in (("freshman","FR"),("sophomore","SO"),("junior","JR"),("senior","SR"),("graduate","GR"),("fifth","5TH")):
        if token in s:return label
    if re.fullmatch(r"r[.-]?fr|rs[ -]?fr|redshirt freshman",s):return "RS-FR"
    if re.fullmatch(r"r[.-]?so|rs[ -]?so|redshirt sophomore",s):return "RS-SO"
    if re.fullmatch(r"r[.-]?jr|rs[ -]?jr|redshirt junior",s):return "RS-JR"
    if re.fullmatch(r"r[.-]?sr|rs[ -]?sr|redshirt senior",s):return "RS-SR"
    return {"fr":"FR","so":"SO","jr":"JR","sr":"SR","gr":"GR","grad":"GR","5th":"5TH","fifth year":"5TH"}.get(s,"")
def flatten(xs):
    if not isinstance(xs,list):return
    for item in xs:
        if not isinstance(item,dict):continue
        if isinstance(item.get("items"),list):
            yield from flatten(item["items"])
        else:yield item
def one_team(tid):
    url=f"https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams/{tid}/roster?season=2027"
    last=""
    for attempt in range(3):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (Portal-Research-QA/1.0)","Accept":"application/json"})
            with urllib.request.urlopen(req,timeout=18) as response:payload=json.load(response)
            people=[]
            for a in flatten(payload.get("athletes",[])):
                pid=str(a.get("id") or a.get("athleteId") or "")
                if members.get(pid)!=str(tid):continue
                exp=a.get("experience") or {}
                if isinstance(exp,str):exp={"displayValue":exp}
                hint=clean(exp.get("abbreviation") or exp.get("displayValue") or a.get("class") or a.get("year"))
                if not hint:continue
                people.append([pid,hint,tid])
            return tid,people,""
        except Exception as exc:
            last=str(exc)[:150];time.sleep(.3*(attempt+1))
    return tid,[],last
entries={};fail=[];bad=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
    for tid,players,error in pool.map(one_team,team_ids):
        if error:fail.append([tid,error])
        for pid,cl,team in players:
            if pid in entries and entries[pid][1]!=cl:bad.append(pid)
            entries[pid]=[cl,team]
assert not bad,bad
out={"schemaVersion":1,"rosterSeason":2027,"targetSeason":"2027-28",
     "source":"ESPN 2026-27 season-specific team roster experience; exact ESPN athlete & team ID",
     "players":entries,
     "coverage":{"roster":len(members),"classified":len(entries),"teamsRequested":len(team_ids),"teamsFailed":len(fail),"errors":fail[:40]}}
(root/"roster_2027_class_evidence.json").write_text(json.dumps(out,separators=(",",":")))
print(json.dumps(out["coverage"]))
if len(entries)<600:raise SystemExit("Insufficient ESPN class evidence; preserve staging and review endpoint")
