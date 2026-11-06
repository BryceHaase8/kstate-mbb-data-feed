#!/usr/bin/env python3
"""Verify exact two approved international NIL priors after real model scoring."""
import argparse,json
from pathlib import Path

def load(p):return json.loads(Path(p).read_text(encoding="utf-8"))["byESPNId"]

def verify(new,old):
    current,previous=load(new),load(old)
    expected={"5454820":(1500000,"INTERNATIONAL_PRO_PRESEASON_STAFF_REVIEWED"),
              "5457323":(2250000,"LATE_ENTRANT_BASELINE_2027")}
    for id,(prior,kind) in expected.items():
        row=current.get(id)
        if row is None or row.get("preseason")!=prior or row.get("anchorType")!=kind or not isinstance(row.get("value"),int):
            raise ValueError("Incorrect approved 2026–27 prior for "+id)
        older=previous.get(id)
        if older and (int(row.get("games") or 0)<int(older.get("games") or 0)
            or float(row.get("minutes") or 0)<float(older.get("minutes") or 0)):
            raise ValueError("Price update removed real season playing time for "+id)
    changed=[id for id,row in previous.items()
             if id in current and id!="5454820"
             and row.get("preseason")!=current[id].get("preseason")]
    if changed:raise ValueError("Unrelated preseason price changed: "+",".join(changed[:10]))
    print("PASS: Morano $1.5M and Szumert $2.25M effective priors; all other old priors intact")

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--new",required=True);p.add_argument("--old",required=True)
    a=p.parse_args();verify(a.new,a.old)
