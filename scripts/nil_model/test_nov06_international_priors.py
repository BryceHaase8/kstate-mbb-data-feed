#!/usr/bin/env python3
"""Offline regression: staff-approved two-player international rebasing after games."""
import copy,json,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from publish_guard import check
from verify_nov06_priors import verify

ROOT=Path(__file__).resolve().parents[2]
def dump(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj));return p

def model(corrected):
    people={str(4000000+i):dict(value=100000,preseason=100000,status="PRESEASON_BASELINE",games=0,minutes=0)
            for i in range(1200)}
    people["5455519"]=dict(value=2500000,preseason=2500000,status="UPDATED",games=2,minutes=40,
                          anchorType="INTERNATIONAL_PRO_PRESEASON_STAFF_REVIEWED")
    people["5454820"]=dict(value=1534000 if corrected else 59509,
                          preseason=1500000 if corrected else 58200,
                          status="UPDATED",games=2,minutes=44,
                          anchorType="INTERNATIONAL_PRO_PRESEASON_STAFF_REVIEWED" if corrected else "FRESHMAN_HS")
    if corrected:
        people["5457323"]=dict(value=2280000,preseason=2250000,status="UPDATED",games=2,minutes=48,
                              anchorType="LATE_ENTRANT_BASELINE_2027")
    return {"season":2027,"policyVersion":3,"generatedAt":"2026-11-06T00:00:00Z",
            "factualGeneratedAt":"2026-11-06T00:00:00Z",
            "byESPNId":people}

def run():
    registered=json.loads((ROOT/"public/stock_watch/opening_price_corrections_2027.json").read_text())
    extras=json.loads((ROOT/"public/stock_watch/late_entrant_baselines_2027.json").read_text())
    assert set(registered["byESPNId"])=={"5455519","5454820"}
    assert registered["byESPNId"]["5454820"]["sourceBaseline"]==58200
    assert registered["byESPNId"]["5454820"]["value"]==1500000
    assert extras["byESPNId"]["5457323"]["value"]==2250000
    with tempfile.TemporaryDirectory() as t:
        root=Path(t)
        prior=dump(root/"old.json",model(False));after=dump(root/"new.json",model(True))
        source=dump(root/"factual.json",{"latestSeason":2027,"generatedAt":"2026-11-06T00:00:00Z"})
        anchor=dump(root/"anchor.json",{"byESPNId":{"5454820":58200,"5455519":155000}})
        history=dump(root/"history.json",{"dates":["2026-11-05"],"months":["2026-11"]})
        opening=dump(root/"corrections.json",registered)
        late=dump(root/"newentrants.json",{"schemaVersion":1,"season":2027,
                      "policy":"LATE_ADDITION_STAFF_APPROVED_OPENING_BASELINE_V1",
                      "byESPNId":{"5457323":extras["byESPNId"]["5457323"]}})
        def guarded():return check(after,prior,source,anchor=anchor,history=history,
                                   opening_corrections=opening,late_entrants=late)
        assert guarded()
        verify(after,prior)
        for key,bad in [("value",1500001),("sourceBaseline",58201),
                        ("effectiveDate","2026-11-05"),("correctionBasis","generic")]:
            fake=copy.deepcopy(registered);fake["byESPNId"]["5454820"][key]=bad
            dump(opening,fake)
            try:guarded()
            except ValueError:pass
            else:raise AssertionError("Unapproved Morano price change "+key)
        dump(opening,registered)
        for field,wrong in [("games",1),("minutes",22)]:
            fake=model(True);fake["byESPNId"]["5454820"][field]=wrong
            dump(after,fake)
            try:guarded()
            except ValueError:pass
            else:raise AssertionError("Real playing time was silently removed")
        dump(after,model(True))
        fake=json.loads(late.read_text());fake["byESPNId"]["5457323"]["value"]=2250001
        dump(late,fake)
        try:guarded()
        except ValueError:pass
        else:raise AssertionError("Unauthorized new NIL anchor accepted")
    print("PASS exact two ESPN IDs, guarded original prior, in-season stats, no other pricing changes")

if __name__=="__main__":run()
