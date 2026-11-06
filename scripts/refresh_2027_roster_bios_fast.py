#!/usr/bin/env python3
"""Fast exact-ESPN-ID roster biography refresh. No NIL, eligibility, or membership writes.
Uses the ESPN current-team roster endpoint consumed by hoopR::espn_mbb_team_roster().
"""
import concurrent.futures as cf
import datetime as dt
import json, re, time, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FAST=ROOT/"research_data/staged/roster_2027_fast_ready.json"
COMPACT=ROOT/"research_data/staged/roster_2027_site_compact_ready.json"
AUDIT=ROOT/"research_data/staged/roster_2027_bio_refresh_audit.json"
URL="https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams/{}?enable=roster"

def fetch(teamid):
    for i in range(2):
        try:
            req=urllib.request.Request(URL.format(teamid),headers={"User-Agent":"KStateRosterBio/1.0","Accept":"application/json"})
            with urllib.request.urlopen(req,timeout=12) as response:
                obj=json.load(response)
            team=obj.get("team") or {}
            athletes=team.get("athletes") or []
            if str(team.get("id"))!=teamid or not isinstance(athletes,list) or len(athletes)<5:
                raise ValueError("wrong team or incomplete roster")
            return teamid,athletes,None
        except (OSError,ValueError,TypeError,KeyError) as exc:
            if i: return teamid,[],str(exc)
            time.sleep(.5)
    return teamid,[],"failed"

def verified_weight(a):
    raw=str(a.get("displayWeight") or "").strip()
    if not raw and a.get("weight") is not None:
        try:raw=str(int(round(float(a["weight"]))))
        except (ValueError,TypeError):pass
    m=re.fullmatch(r"\s*(\d{2,3})\s*(?:lbs?\.?|pounds?)?\s*",raw,re.I)
    if not m or not 90<=int(m[1])<=400:return ""
    return m[1]+" lbs"

def verified_headshot(a):
    h=a.get("headshot") or {}
    url=h.get("href","") if isinstance(h,dict) else (h if isinstance(h,str) else "")
    url=str(url).strip()
    return url if url.startswith("https://") and "espn" in url.lower() and re.search(r"\.(png|jpg|jpeg|webp)([?#]|$)",url,re.I) else ""

def main():
    fast=json.loads(FAST.read_text());compact=json.loads(COMPACT.read_text())
    assert fast.get("schemaVersion")==3 and fast.get("rosterSeason")==2027
    rows=fast["players"];teams=fast["teams"]
    assert len(rows)>=5500 and len(teams)>=350
    old={str(row[0]):list(row) for row in rows}
    assert len(old)==len(rows)
    previous={str(p["espnAthleteId"]):p for p in compact["players"]}
    roster={};failures={};new_ids={};duplicates=[]
    with cf.ThreadPoolExecutor(max_workers=16) as pool:
        for future in cf.as_completed([pool.submit(fetch,tid) for tid in teams]):
            tid,athletes,error=future.result()
            if error:failures[tid]=error;continue
            for athlete in athletes:
                aid=str(athlete.get("id") or "")
                if not aid.isdigit():continue
                if aid not in old:
                    new_ids[aid]={"id":aid,"name":athlete.get("displayName"),"teamId":tid}
                    continue
                if str(old[aid][2])!=tid:continue
                if aid in roster:duplicates.append(aid)
                else:roster[aid]=athlete
    if len(teams)-len(failures)<300 or duplicates:
        raise RuntimeError("Aborted incomplete source/duplicate IDs: %s/%s teams, %s duplicates"%
            (len(teams)-len(failures),len(teams),len(duplicates)))
    count={"weightFilled":0,"weightChanged":0,"headshotFilled":0,"headshotChanged":0,"heightFilled":0}
    old_missing_w=sum(not str(row[5] or "").strip() for row in rows)
    old_missing_h=sum(not (previous.get(id,{}).get("headshot") or "") for id in old)
    output=[];objects=[];examples=[]
    for original in rows:
        row=list(original);aid=str(row[0]);bio=roster.get(aid) or {};was=previous.get(aid,{})
        before_w=str(row[5] or "").strip();before_h=str(was.get("headshot") or "").strip()
        weight=verified_weight(bio);headshot=verified_headshot(bio)
        if weight and weight!=before_w:
            row[5]=weight
            key="weightFilled" if not before_w else "weightChanged"
            count[key]+=1
            if len(examples)<30:examples.append({"id":aid,"name":row[1],"field":"weight","before":before_w,"after":weight})
        if not row[4] and bio.get("displayHeight"):
            row[4]=str(bio["displayHeight"]);count["heightFilled"]+=1
        if headshot and headshot!=before_h:
            key="headshotFilled" if not before_h else "headshotChanged"
            count[key]+=1
            if len(examples)<30:examples.append({"id":aid,"name":row[1],"field":"headshot","before":before_h,"after":headshot})
        finalh=headshot or before_h
        # Tenth column is optional official headshot. Original nine columns untouched.
        row=row[:9]+[finalh]
        assert row[:4]==original[:4] and row[6:9]==original[6:9]
        output.append(row)
        objects.append({
          "espnAthleteId":aid,"name":row[1],"team":teams[str(row[2])],
          "teamId":str(row[2]),"position":row[3],"height":row[4],
          "weight":row[5] or None,"headshot":finalh or None,
          "birthPlace":row[7],"eligibilityEstimate":row[6],
          "eligibilityTargetSeason":"2027-28",
          "identityStatus":was.get("identityStatus") or ("HISTORY_OR_BIO_REVIEW" if row[8]==2 else "ESPN_ID_WITH_BIO"),
          "teamReadiness":was.get("teamReadiness") or ("ROSTER_NEEDS_REVIEW" if row[8]!=0 else "UPDATED_NEEDS_FINAL_COMPLETENESS_QA")
        })
    assert len(output)==len(objects)==len(old)
    fast["players"]=output;compact["players"]=objects;compact["totalTeams"]=len(teams)
    audit={"timestamp":dt.datetime.now(dt.timezone.utc).isoformat(),
      "method":"ESPN current team roster (same endpoint as hoopR espn_mbb_team_roster)",
      "playersBefore":len(rows),"playersAfter":len(output),
      "teamsRequested":len(teams),"teamsVerified":len(teams)-len(failures),
      "failedTeams":failures,
      "missingWeightBefore":old_missing_w,
      "missingWeightAfter":sum(not str(r[5] or "").strip() for r in output),
      "missingHeadshotBefore":old_missing_h,
      "missingHeadshotAfter":sum(not p["headshot"] for p in objects),
      "changes":count,"newIdsNotApplied":list(new_ids.values()),
      "membershipChanged":False,"eligibilityChanged":False,"nilChanged":False,
      "examples":examples}
    FAST.write_text(json.dumps(fast,ensure_ascii=False,separators=(",",":"))+"\n")
    COMPACT.write_text(json.dumps(compact,ensure_ascii=False,separators=(",",":"))+"\n")
    AUDIT.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+"\n")
    print("FAST BIO REFRESH",json.dumps({k:v for k,v in audit.items() if k not in ("examples","failedTeams","newIdsNotApplied")}),flush=True)
if __name__=="__main__":main()

# Re-run 2026-11-05 national ESPN roster biography snapshot.

# 2026-11-06 fast full-roster recheck; append-only research audit; never mutate NIL.
