#!/usr/bin/env python3
"""Independent aggregate schema and rate sanity checks; no production writes."""
from pathlib import Path
from collections import Counter
import json,math
base=Path("research_data/staged/portal_onoff_2026")
manifest=json.loads((base/"manifest.json").read_text())
assert manifest["season"]==2026 and manifest["modulo"]==128
assert manifest["gamesVerified"]>=5400,manifest
assert manifest["verifiedPlayerGames"]>=100000,manifest
assert manifest["playersWithVerifiedGameSplits"]>=4700,manifest
seen=set()
tot=Counter()
odd=[]
for i in range(128):
    j=json.loads((base/f"onoff_{i:03d}.json").read_text())
    assert j["schemaVersion"]==1 and j["season"]==2026 and j["shard"]==i
    for pid,r in j["players"].items():
        assert pid.isdigit() and int(pid)%128==i and pid not in seen,pid
        seen.add(pid)
        games=r["games"]
        assert 0<games<=45,games
        minutes=r["on"]["minutes"]+r["off"]["minutes"]
        assert 38.0*games<=minutes<=45.5*games,(pid,games,minutes)
        onMinutes=r["on"]["minutes"]
        if abs(onMinutes-r["verifiedBoxMinutes"])>2.2*games:
            odd.append((pid,onMinutes,r["verifiedBoxMinutes"]))
        for state in ("on","off"):
            side=r[state]
            for name in ("off","def"):
                d=side[name]
                assert all(math.isfinite(v) and v>=0 for v in d.values()),(pid,state,name)
                fga=d.get("fga",0);fgm=d.get("fgm",0)
                assert fgm<=fga+1e-9,(pid,state,name)
                assert d.get("threeA",0)+d.get("twoA",0)==fga,(pid,state,name)
                assert d.get("threeM",0)+d.get("twoM",0)==fgm,(pid,state,name)
                assert d.get("ftm",0)<=d.get("fta",0),(pid,state,name)
                actual=d.get("twoM",0)*2+d.get("threeM",0)*3+d.get("ftm",0)
                assert abs(actual-d.get("pts",0))<1e-6,(pid,state,name,actual,d.get("pts"))
        tot["games"]+=games
        tot["minutes"]+=onMinutes
        tot["athletes"]+=1
assert not odd,odd[:12]
assert tot["athletes"]==manifest["playersWithVerifiedGameSplits"]
assert tot["games"]==manifest["verifiedPlayerGames"]
print("PASS",json.dumps(dict(tot)),"full-stats arithmetic, minute bounds, identity uniqueness, national coverage")
