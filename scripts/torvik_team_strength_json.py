#!/usr/bin/env python3
"""Research-only single daily Torvik team-results JSON download; no crawling."""
import argparse,csv,datetime as dt,hashlib,json,re,unicodedata
from pathlib import Path
from urllib.request import Request,urlopen

# Zero-based positions checked against 2026 CSV header and user's 2027 JSON.
FIELDS={"rank":0,"team":1,"conf":2,"record":3,"adjOE":4,"offRank":5,
        "adjDE":6,"defRank":7,"barthag":8,"overallRank":9,"adjTempo":44}
ALIASES={"Connecticut":"UConn","Illinois Chicago":"UIC","Miami FL":"Miami Hurricanes",
         "McNeese St.":"McNeese","Long Island":"LIU","Arkansas Little Rock":"Little Rock",
         "N.C. A&T":"North Carolina A&T","N.C. Central":"North Carolina Central"}

def normal(s):
    s=unicodedata.normalize("NFKD",str(s)).encode("ascii","ignore").decode("ascii").lower()
    s=s.replace("&"," and ").replace("'","")
    s=re.sub(r"^st[.]?\s+","saint ",s)
    s=re.sub(r"\bst[.](?=\W|$)","state",s)
    return re.sub(r"\s+"," ",re.sub(r"[^a-z0-9]+"," ",s)).strip()

def parse(raw):
    if not isinstance(raw,list) or not 340<=len(raw)<=400:
        raise ValueError("Unexpected team count; stop rather than overwrite the existing snapshot")
    data=[]
    for n,r in enumerate(raw):
        if not isinstance(r,list) or len(r)!=45:
            raise ValueError(f"Unexpected schema on row {n}: expected exactly 45 fields")
        try:
            rank=int(r[0]);team=str(r[1]).strip();conf=str(r[2]);record=str(r[3])
            oe=float(r[4]);de=float(r[6]);bh=float(r[8]);pace=float(r[44])
            if (not team or not conf or not re.fullmatch(r"\d+-\d+",record) or
                not 1<=rank<=400 or not 65<=oe<=155 or not 65<=de<=140 or
                not 0<=bh<=1 or not 50<=pace<=90):
                raise ValueError("out of range")
        except (ValueError,TypeError,IndexError) as ex:
            raise ValueError(f"Unexpected team values in row {n}") from ex
        data.append({"torvikTeam":team,"conference":conf,"record":record,
                     "rank":rank,"adjOE":round(oe,5),"adjDE":round(de,5),
                     "adjEM":round(oe-de,5),"barthag":round(bh,7),
                     "adjTempo":round(pace,5),"espnTeamId":None})
    if len(set(x["torvikTeam"] for x in data))!=len(data):
        raise ValueError("Duplicate Torvik names")
    if len(set(x["rank"] for x in data))!=len(data):
        raise ValueError("Duplicate ranks")
    return data

def espn_directory(p):
    latest={}
    with open(p,encoding="utf-8-sig",newline="") as f:
        for r in csv.DictReader(f):
            tid=(r.get("team_id") or "").strip()
            name=(r.get("team_name") or "").strip()
            try:season=int(r.get("season",""))
            except ValueError:continue
            if tid and name and (tid not in latest or season>latest[tid][0]):
                latest[tid]=(season,name)
    return [(tid,n,normal(n)) for tid,(_,n) in latest.items()]

def crosswalk(rows,directory):
    used=set();unmatched=[];ambiguous=[];matched=0
    for r in rows:
        team=r["torvikTeam"]
        q=normal(ALIASES.get(team,team))
        candidates=[(tid,n) for tid,n,k in directory if k==q or k.startswith(q+" ")]
        if len(candidates)==1 and candidates[0][0] not in used:
            r["espnTeamId"]=candidates[0][0]
            used.add(candidates[0][0]);matched+=1
        elif len(candidates)>1:
            ambiguous.append({"torvikTeam":team,"candidates":candidates})
        else:
            unmatched.append(team)
    return matched,unmatched,ambiguous

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--season",type=int,required=True)
    p.add_argument("--fixture",default=None)
    p.add_argument("--espn-csv",default="data/current_player_season_stats.csv")
    p.add_argument("--out",default="research_qa/torvik_team_strength_2027.json")
    p.add_argument("--qa",default="research_qa/torvik_team_strength_2027_qa.json")
    a=p.parse_args()
    url=f"https://barttorvik.com/{a.season}_team_results.json"
    if a.fixture:
        rawbytes=Path(a.fixture).read_bytes()
        rawtext=rawbytes.decode("utf-8-sig")
        if rawtext.lstrip().startswith(chr(96)):
            rawtext=rawtext[rawtext.index("["):rawtext.rindex("]")+1]
    else:
        req=Request(url,headers={"Accept":"application/json",
            "User-Agent":"KState-MBB-Research/1.0 (one bulk JSON request/day; respect publisher access policy)"})
        with urlopen(req,timeout=30) as response:
            rawbytes=response.read(2_500_001)
            if len(rawbytes)>2_500_000:raise ValueError("Unexpectedly large file")
        rawtext=rawbytes.decode("utf-8-sig")
    data=parse(json.loads(rawtext))
    matched,unmatched,ambiguous=crosswalk(data,espn_directory(a.espn_csv))
    preseason=all(r["record"]=="0-0" for r in data)
    hash=hashlib.sha256(rawbytes).hexdigest()
    print(f"Torvik {a.season}: {len(data)} teams, {matched} ESPN matches, {len(unmatched)} unmatched, {len(ambiguous)} ambiguous, preseason={preseason}")
    print("Unmatched sample:",unmatched[:25])
    if matched<len(data)*.80:
        raise ValueError("Match rate below 80% safety gate; do not save incomplete source")
    op=Path(a.out);qp=Path(a.qa)
    op.parent.mkdir(exist_ok=True,parents=True);qp.parent.mkdir(exist_ok=True,parents=True)
    if op.exists():
        try:
            old=json.loads(op.read_text())
            if old.get("sourceSha256")==hash:
                print("Unchanged source; no rewrite");return
        except (ValueError,OSError):pass
    now=dt.datetime.now(dt.timezone.utc).isoformat()
    snapshot={"schemaVersion":1,"source":"Bart Torvik published bulk JSON","sourceUrl":url,
       "season":a.season,"sourceSha256":hash,"retrievedAtUTC":now,
       "ratingsStage":"PRESEASON_PROJECTION" if preseason else "IN_SEASON_OR_FINAL",
       "matchedESPNTeams":matched,"teamCount":len(data),"teams":data}
    qa={"season":a.season,"teams":len(data),"matched":matched,"unmatched":unmatched,
       "ambiguous":ambiguous,"preseason":preseason,"sourceSha256":hash,
       "note":"Research only. A 0-0 rating is a preseason projection, not observed season efficiency."}
    qp.write_text(json.dumps(qa,indent=2)+"\n")
    op.write_text(json.dumps(snapshot,separators=(",",":"))+"\n")
    print("Saved research snapshot and ESPN-name match QA")
if __name__=="__main__":main()
