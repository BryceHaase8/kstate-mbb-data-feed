#!/usr/bin/env python3
"""Offline regression checks; never makes a Torvik HTTP request."""
import csv, json, subprocess, sys, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts"/"torvik_bulk_daily.py"
CONTEXT=ROOT/"public"/"research_team_context.json"
d=json.loads(CONTEXT.read_text())["teams"]["2026"]
assert len(d)>=360, "Expected ESPN D-I directory"
rows=[]
for i, (tid, record) in enumerate(d.items(),1):
    name=record["name"]
    special={"Kansas State Wildcats":"Kansas St.","UConn Huskies":"Connecticut",
        "Miami Hurricanes":"Miami FL","Florida Gators":"Florida",
        "Florida State Seminoles":"Florida St.","Penn Quakers":"Penn"}
    name=special.get(name,name)
    row=[0]*45
    row[0]=i;row[1]=name;row[2]="B12";row[3]="0-0"
    row[4]=110.;row[5]=55;row[6]=100.;row[7]=60;row[8]=0.7;row[9]=i;row[44]=70.
    rows.append(row)
# Only one school represented for each ESPN team. The same numeric layout
# as the user's 45-column 2027 JSON, but names intentionally mixed/aliased.
assert 340<=len(rows)<=400
with tempfile.TemporaryDirectory() as td:
    p=Path(td)
    fixture=p/"fixture.json";snapshot=p/"last_good.json";status=p/"status.json"
    fixture.write_text(json.dumps(rows))
    args=[sys.executable,str(SCRIPT),"--season","2027","--fixture",str(fixture),
          "--snapshot",str(snapshot),"--status",str(status),
          "--espn-context",str(CONTEXT)]
    p1=subprocess.run(args,capture_output=True,text=True)
    assert p1.returncode==0,(p1.stdout,p1.stderr)
    outcome=json.loads(snapshot.read_text())
    stat=json.loads(status.read_text())
    assert outcome["ratingsStage"]=="PRESEASON_PROJECTION"
    assert outcome["teamCount"]==len(rows)
    assert stat["status"]=="ok"
    assert outcome["matchedESPNTeams"]>=.90*len(rows),(
        outcome["matchedESPNTeams"],len(rows),outcome.get("unmatchedTeams",[])[:35])
    assert [x["espnTeamId"] for x in outcome["teams"] if x["torvikTeam"]=="Kansas St."] == ["2306"]
    old=snapshot.read_bytes()
    # Exact fixture unchanged -> snapshot hash unchanged.
    p2=subprocess.run(args,capture_output=True,text=True)
    assert p2.returncode==0 and snapshot.read_bytes()==old
    # Bad JSON structure cannot clobber valid snapshot.
    fixture.write_text('{"error":"HTML/login payload"}')
    p3=subprocess.run(args,capture_output=True,text=True)
    assert p3.returncode==0 and snapshot.read_bytes()==old
    assert json.loads(status.read_text())["status"]=="stale_fallback"
    # Without prior snapshot, invalid data must NOT silently succeed.
    snapshot.unlink()
    p4=subprocess.run(args,capture_output=True,text=True)
    assert p4.returncode==3 and not snapshot.exists()
    # Headered CSV fallback uses same 45 positional fields and checks headers.
    hdr=["x"+str(j) for j in range(45)]
    hdr[:4]=["rank","team","conf","record"]
    hdr[4]="adjoe";hdr[6]="adjde";hdr[44]="adjt"
    csvfile=p/"fixture.csv"
    with csvfile.open("w",newline="") as f:
        writer=csv.writer(f);writer.writerow(hdr);writer.writerows(rows)
    args[args.index(str(fixture))]=str(csvfile)
    p5=subprocess.run(args,capture_output=True,text=True)
    assert p5.returncode==0,(p5.stdout,p5.stderr)
    assert json.loads(snapshot.read_text())["sourceFormat"]=="csv"
    print("PASS: sample JSON+CSV ingestion, >90% crosswalk, K-State ID, no-op hashing, stale fallback, no silent malformed overwrite.")
