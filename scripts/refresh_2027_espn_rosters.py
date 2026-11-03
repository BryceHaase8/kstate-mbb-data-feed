#!/usr/bin/env python3
"""2026-27 ESPN D-I roster recheck, add-only and ESPN-ID keyed.

Never changes an existing identity's staff-owned fields, frozen NIL values,
or eligibility estimates. A successful team roster can add an ESPN ID; a
partial/failed response cannot delete one.
"""
import concurrent.futures as cf
import datetime as dt
import json
import random
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/"data/roster_2027_advanced.json"
NEW_CLASS=ROOT/"data/roster_2027_class_evidence.json"
REPORT=ROOT/"data/roster_additions_2027_20261103.json"
FATAL_MIN_TEAMS=340
URL="https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams/{}/roster?season=2027"
FALLBACK_URL="https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams/{}?enable=roster"
AGENT="KStateBasketballRosterQA/1.0 (2026-27 research)"
CLASS_YEARS={"FR":4,"SO":3,"JR":2,"SR":0,"GR":0,"GS":0,"FRESHMAN":4,
             "SOPHOMORE":3,"JUNIOR":2,"SENIOR":0,"GRADUATE":0}
def roster(team_id):
    url=URL.format(team_id)
    for attempt in range(5):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":AGENT,"Accept":"application/json"})
            source="ESPN_2027_SEASON_ROSTER_ID"
            try:
                with urllib.request.urlopen(req,timeout=22) as response:
                    data=json.load(response)
                if int((data.get("season") or {}).get("year") or 0)!=2027:
                    raise ValueError("ESPN returned wrong season for "+str(team_id))
                athletes=data.get("athletes") or []
            except urllib.error.HTTPError as err:
                if err.code!=404:raise
                # ESPN sometimes fails the season-specific team route while
                # its current team roster is available (Mercer #2382, Nov 3).
                # This alternate feed supplies identity/size, NOT class-year
                # evidence: absent class remains explicitly review-required.
                alternate=urllib.request.Request(FALLBACK_URL.format(team_id),
                    headers={"User-Agent":AGENT,"Accept":"application/json"})
                with urllib.request.urlopen(alternate,timeout=22) as response:
                    data=json.load(response)
                team=data.get("team") or {}
                if str(team.get("id"))!=str(team_id):
                    raise ValueError("Alternate ESPN roster returned wrong team "+str(team_id))
                athletes=team.get("athletes") or []
                source="ESPN_CURRENT_TEAM_ROSTER_FALLBACK_SEASON_404"
            if not isinstance(athletes,list) or len(athletes)<5:
                raise ValueError("ESPN returned empty/incomplete team "+str(team_id))
            valid=[]
            for a in athletes:
                pid=str(a.get("id") or "")
                name=str(a.get("displayName") or a.get("fullName") or "").strip()
                if not pid.isdigit() or not name:continue
                ex=a.get("experience") or {}
                school_class=str(ex.get("abbreviation") or "").upper().strip()
                if not school_class:
                    display=str(ex.get("displayValue") or "").upper()
                    school_class=next((short for short,full in (("FR","FRESHMAN"),("SO","SOPHOMORE"),("JR","JUNIOR"),("SR","SENIOR"),("GR","GRADUATE")) if full in display),"")
                pos=str((a.get("position") or {}).get("abbreviation") or "")
                place=a.get("birthPlace") or {}
                hometown=str(place.get("displayText") or ", ".join(x for x in [place.get("city"),place.get("state"),place.get("country")] if x) or "")
                valid.append(dict(id=pid,name=name,teamId=str(team_id),position=pos,
                     height=str(a.get("displayHeight") or ""),weight=str(a.get("displayWeight") or ""),
                     hometown=hometown,schoolClass=school_class,active=bool(a.get("active",True)),
                     source=source))
            if len(valid)<5:raise ValueError("No valid roster athletes for "+str(team_id))
            return str(team_id),valid,None
        except (OSError,ValueError,TypeError,KeyError) as e:
            if attempt==4:return str(team_id),[],str(e)
            time.sleep(min(10,(attempt+1)*1.5)+random.random())
    return str(team_id),[],"Unexpected no result"

def main():
    old=json.loads(OLD.read_text())
    assert old["schemaVersion"]==3 and old["rosterSeason"]==2027 and len(old["teams"])>=350
    old_rows={str(row[0]):list(row) for row in old["players"]}
    teams=old["teams"]
    results=[]
    # Moderate concurrency and retries reduce rate-limit risk.
    with cf.ThreadPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(roster,team_id) for team_id in sorted(teams,key=int)]
        for future in cf.as_completed(futures):results.append(future.result())
    successful=[result for result in results if result[2] is None]
    if len(successful)<FATAL_MIN_TEAMS:
        raise RuntimeError("Only %d/%d team rosters verified; preserved old roster without publishing" %
                           (len(successful),len(teams)))
    found={}
    class_by_id={}
    duplicate=[]
    for team_id,athletes,_ in sorted(successful,key=lambda row:int(row[0])):
        for a in athletes:
            pid=a["id"]
            if pid in found:
                duplicate.append(dict(id=pid,teams=[found[pid]["teamId"],team_id]))
                continue
            found[pid]=a
            if a["schoolClass"]:
                class_by_id[pid]=[a["schoolClass"],team_id]
    if duplicate:raise RuntimeError("ESPN athlete ID listed across multiple D-I teams: "+str(duplicate[:8]))
    additions={}
    updated={key:list(row) for key,row in old_rows.items()}
    for pid,a in sorted(found.items(),key=lambda pair:int(pair[0])):
        if pid in updated:
            # Existing entries: retain eligibility/staff research decision; team
            # school changes can be validated separately rather than silently moved.
            continue
        classification=a["schoolClass"]
        years=CLASS_YEARS.get(classification,0)
        code=0 if classification in CLASS_YEARS else 2
        row=[pid,a["name"],a["teamId"],a["position"],a["height"],a["weight"],
             years,a["hometown"],code]
        updated[pid]=row
        additions[pid]={"name":a["name"],"teamId":a["teamId"],"team":teams[a["teamId"]],
             "position":a["position"],"height":a["height"],"weight":a["weight"],
             "espnClass":classification,"eligibilityYearsEstimate":years,
             "eligibilityStatus":"RESEARCH_ONLY_NOT_COURT_RULING",
             "source":a["source"],"rosterRow":row}
    combined=sorted(updated.values(),key=lambda row:(int(row[2]),str(row[1]).lower(),int(row[0])))
    if len(combined)<len(old_rows) or len({str(x[0]) for x in combined})!=len(combined):
        raise RuntimeError("Data loss or duplicate ESPN roster IDs")
    old["players"]=combined
    # Keep existing exact-ID class evidence whenever ESPN doesn't supply new class.
    if NEW_CLASS.exists():
        prior_class=json.loads(NEW_CLASS.read_text()).get("players") or {}
    else:
        prior_class={}
    prior_class.update(class_by_id)
    evidence={"schemaVersion":1,"rosterSeason":2027,"targetSeason":"2027-28",
              "source":"ESPN 2026-27 season-specific current team rosters",
              "players":dict(sorted(prior_class.items(),key=lambda z:int(z[0]))),
              "coverage":{"roster":len(combined),"classified":len(prior_class),
                          "teamsRequested":len(teams),"teamsSucceeded":len(successful),
                          "teamsFailed":len(results)-len(successful),
                          "errors":[{"teamId":id,"reason":err} for id,_,err in results if err]}}
    report={"schemaVersion":1,"season":2027,"source":"Official ESPN 2026-27 team rosters",
            "asOf":dt.datetime.now(dt.timezone.utc).isoformat(),
            "previousRosterPlayers":len(old_rows),"currentRosterPlayers":len(combined),
            "newESPNIDs":len(additions),"teamsRequested":len(teams),
            "teamsVerified":len(successful),"teamsFailed":len(results)-len(successful),
            "additions":additions,"note":"Roster identity only; no automatic NIL approval or legal eligibility certification."}
    OLD.write_text(json.dumps(old,ensure_ascii=False,separators=(",",":"))+"\n")
    NEW_CLASS.write_text(json.dumps(evidence,ensure_ascii=False,separators=(",",":"))+"\n")
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("ESPN ROSTER PASS",json.dumps({k:report[k] for k in
         ["previousRosterPlayers","currentRosterPlayers","newESPNIDs","teamsRequested","teamsVerified","teamsFailed"]}))
    for pid,entry in list(additions.items())[:40]:print("NEW",pid,entry["name"],entry["team"],entry["espnClass"])
if __name__=="__main__":
    main()
