#!/usr/bin/env python3
"""Exact-ESPN-ID national roster comparison; never assigns staff eligibility/NIL."""
import argparse,json,datetime
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument("--old",required=True);p.add_argument("--new",required=True);p.add_argument("--out",required=True)
a=p.parse_args()
old=json.loads(Path(a.old).read_text())
new=json.loads(Path(a.new).read_text())
def index(data):
    rows=data["players"]
    idx={str(x["espnAthleteId"]):x for x in rows}
    if len(idx)!=len(rows):raise ValueError("Duplicate ESPN athlete IDs")
    return idx
before=index(old);after=index(new)
def describe(id,x):
    return {"espnAthleteId":id,"name":x.get("name"),"teamId":str(x.get("teamId")),"team":x.get("team"),"headshot":x.get("headshot")}
added=[describe(id,after[id]) for id in sorted(after.keys()-before.keys(),key=int)]
removed=[describe(id,before[id]) for id in sorted(before.keys()-after.keys(),key=int)]
changed=[]
meta=[]
for id in sorted(after.keys() & before.keys(),key=int):
    x=before[id];y=after[id]
    if str(x.get("teamId"))!=str(y.get("teamId")):
        changed.append({"espnAthleteId":id,"nameBefore":x.get("name"),"nameAfter":y.get("name"),"from":x.get("team"),"to":y.get("team"),"fromId":str(x.get("teamId")),"toId":str(y.get("teamId"))})
    fields={k:{"before":x.get(k),"after":y.get(k)} for k in ("name","position","jersey","height","weight","headshot") if x.get(k)!=y.get(k)}
    if fields:meta.append({"espnAthleteId":id,"name":y.get("name"),"team":y.get("team"),"changedFields":fields})
res={"comparisonAsOf":datetime.datetime.now(datetime.timezone.utc).isoformat(),"baselinePlayers":len(before),"currentPlayers":len(after),"teams":new.get("totalTeams"),
     "addedCount":len(added),"removedCount":len(removed),"transfersAmongRetainedCount":len(changed),"metadataChangedCount":len(meta),
     "added":added,"removed":removed,"teamChanges":changed,"metadataChanges":meta,
     "identityPolicy":"ESPN-ID-only; never infer a transfer or value from player names"}
if len(added)>200 or len(removed)>200 or len(changed)>100:raise ValueError("Implausibly large roster delta; do not publish")
out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(res,indent=2,ensure_ascii=False))
print(json.dumps({k:v for k,v in res.items() if k.endswith("Count") or k in ("baselinePlayers","currentPlayers","teams","comparisonAsOf")}))
