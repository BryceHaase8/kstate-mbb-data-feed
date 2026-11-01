#!/usr/bin/env python3
"""Read-only 2026->2027 ESPN athlete-ID continuity audit, no staff or data writes."""
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

def norm(s):
    s = unicodedata.normalize("NFKD",str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c)).casefold()
    s = re.sub(r"\b(ii|iii|iv|v|jr|sr)\b", "", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()

roster = json.loads(Path("research_data/staged/roster_2027_fast_ready.json").read_text())["players"]
facts = json.loads(Path("public/portal_factual_data.json").read_text())["players"]
prev = defaultdict(list)
for pid, obj in facts.items():
    v = next((s for s in obj.get("seasons",[]) if int(s.get("season") or 0)==2026), None)
    if not v or not (float(v.get("gp") or 0)>0):
        continue
    prev[norm(v.get("name"))].append({"id": str(pid),"name":v.get("name"),"teamId":str(v.get("teamId") or ""),
                                   "team":v.get("team"),"jersey":v.get("jersey"),
                                   "gp":int(v.get("gp") or 0),"min":float(v.get("minutes") or 0)})
cur = defaultdict(list)
for row in roster:
    cur[norm(row[1])].append({"id":str(row[0]),"name":row[1],"teamId":str(row[2]),"yrs":row[6]})
sameTeam = []; differentTeam = []; ambiguities=[]
for name, new in cur.items():
    old = prev.get(name, [])
    if not old:
        continue
    if len(new)!=1 or len(old)!=1:
        if {x["id"] for x in new}!={x["id"] for x in old}:
            ambiguities.append({"name":name,"old":old,"new":new})
        continue
    a,b=old[0],new[0]
    if a["id"]==b["id"]:
        continue
    record={"name":name,"old":a,"current":b}
    if a["teamId"]==b["teamId"]:
        sameTeam.append(record)
    else:
        differentTeam.append(record)
print("2026 athlete records",sum(len(v) for v in prev.values()))
print("2027 roster",len(roster))
print("Unique normalized name, different ESPN ID, same team:",len(sameTeam))
print("Unique normalized name, different ESPN ID, other team:",len(differentTeam))
print("Ambiguous name collisions needing manual review:",len(ambiguities))
print("HIGH PRIORITY SAME-TEAM ID DRIFT:")
for row in sorted(sameTeam,key=lambda r:r["name"]):
    print(json.dumps(row,ensure_ascii=False))
print("DIFFERENT-TEAM ID DRIFT (MANUAL REVIEW):")
for row in sorted(differentTeam,key=lambda r:r["name"]):
    print(json.dumps(row,ensure_ascii=False))
print("AMBIGUITIES:",json.dumps(ambiguities[:35],ensure_ascii=False))
assert len(roster)>5400 and len(facts)>10000
