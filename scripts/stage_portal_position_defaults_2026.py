#!/usr/bin/env python3
"""Produce compact, staff-agnostic ESPN ID -> estimated primary/secondary position.
These are *model defaults*, never writes to the staff evaluation sheet.
"""
from pathlib import Path
import json,collections
folder=Path("research_data/staged/portal_positions_2026")
manifest=json.loads((folder/"manifest.json").read_text())
assert manifest["season"]==2026 and manifest["playersWithRoleTime"]>=4000
result={}
qa=collections.Counter()
for shard in range(128):
    doc=json.loads((folder/f"positions_{shard:03d}.json").read_text())
    assert doc["shard"]==shard and doc["modulo"]==128
    for aid,(roles,verified,total,games,known) in doc["players"].items():
        qa["total"]+=1
        if verified < 60 or verified/total < .50 or games < 3:
            qa["insufficientSample"]+=1
            continue
        r=sorted(range(5), key=lambda i:(-roles[i],i))
        primary=str(r[0]+1)
        secondary=str(r[1]+1) if roles[r[1]]/verified>=.15 and roles[r[1]]>=15 else ""
        result[aid]=[primary,secondary,round(verified,1),round(verified/total,3)]
        qa["qualified"]+=1
        qa["primary_"+primary]+=1
        if secondary:qa["hasSecondary"]+=1
assert len(result)>3000,qa
out={"schemaVersion":1,"season":2026,"source":"ESPN 2025-26 box-minute-validated five-player lineup position estimates",
     "rule":"At least 60 verified minutes, 50% season time, 3 games; secondary at least 15% and 15 minutes",
     "byESPNId":result,"qa":dict(qa)}
(folder/"position_defaults_2026.json").write_text(json.dumps(out,separators=(",",":")))
(folder/"position_defaults_2026.js").write_text("window.PORTAL_POSITION_DEFAULTS_2026="+json.dumps(out,separators=(",",":"))+";\n")
print("PASS",json.dumps(qa))
