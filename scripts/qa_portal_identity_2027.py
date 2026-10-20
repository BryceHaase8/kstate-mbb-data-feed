#!/usr/bin/env python3
"""Offline readiness QA for public ESPN player/team IDs and historical profile joins.
Does not alter rosters, eligibility overrides, or the public production feed.
"""
from pathlib import Path
import json
import csv
import gzip
from collections import Counter

ROOT = Path("research_data/staged")
roster = json.loads((ROOT / "roster_2027_fast_ready.json").read_text())
classes = json.loads((ROOT / "roster_2027_class_evidence.json").read_text())
impacts = json.loads((ROOT / "impact_v3_2026_all_ready.json").read_text())
r = roster["players"]
ids = [str(x[0]) for x in r]
assert len(r) > 5400 and len(ids) == len(set(ids))
teams = roster["teams"]
assert len(teams) == 365, len(teams)
assert all(len(x) >= 7 and str(x[2]) in teams for x in r)
assert all(isinstance(x[6], int) and 0 <= x[6] <= 5 for x in r)
byid = {str(x[0]): x for x in r}
class_data = classes["players"]
bad_class_joins = [(pid, v) for pid, v in class_data.items()
                   if pid not in byid or str(v[1]) != str(byid[pid][2])]
assert not bad_class_joins, bad_class_joins[:5]

impact_ids = [str(x[0]) for x in impacts["players"]]
assert len(impact_ids) == len(set(impact_ids))
impact_map = {str(x[0]): x for x in impacts["players"]}
historical = {}
with gzip.open(ROOT / "player_seasons_2020_2026.csv.gz", "rt", encoding="utf-8", newline="") as f:
    for row in csv.DictReader(f):
        athlete = str(row["athlete_id"])
        historical.setdefault(athlete, []).append(int(row["season"]))
current = set(ids)
historical_current = current.intersection(historical)
hist_last_2026 = {k for k in historical_current if 2026 in historical[k]}
new_without_history = current - set(historical)
zero_with_prior = [p[0] for p in r if p[6] == 0 and str(p[0]) in historical]
class_hist_conflicts = []
for pid, (c, tid) in class_data.items():
    yrs = historical.get(pid, [])
    if c == "FR" and len(yrs) >= 2:
        class_hist_conflicts.append(pid)
class_counts = dict(sorted(Counter(v[0] for v in class_data.values()).items()))
zeros = [p for p in r if p[6] == 0]
assert all(str(p[0]) in current for p in zeros)
report = {
    "status": "PASS",
    "scope": "public record integrity only; no staff valuation or eligibility correctness claim",
    "currentRosterPlayers": len(r),
    "teams": len(teams),
    "uniqueAthleteIds": len(current),
    "exactCurrentClassIds": len(class_data),
    "classCoveragePercent": round(100 * len(class_data) / len(r), 2),
    "missingClassIds": len(current - set(class_data)),
    "classCounts": class_counts,
    "preexisting2020_26HistoryMatched": len(historical_current),
    "currentRosterWith2025_26Stats": len(hist_last_2026),
    "currentRosterWithNoD1BoxHistory": len(new_without_history),
    "zeroEligibilityPlanningProxies": len(zeros),
    "zeroYearEstimatesWithHistoricalStats": len(zero_with_prior),
    "impact2026AllScored": len(impact_map),
    "impact2026MatchedCurrent": len(set(impact_map) & current),
    "flaggedFreshmenWithMultipleDISeasons": len(class_hist_conflicts),
    "freshmanClassReviewExamples": class_hist_conflicts[:12],
    "sourceEligibilityEstimatesAreNotOfficialRulings": True
}
p = Path("research_qa/roster_integration/current_identity_crosswalk_qa.json")
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
