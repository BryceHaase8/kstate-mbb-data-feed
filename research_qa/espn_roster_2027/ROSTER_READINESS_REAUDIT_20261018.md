# ESPN 2026–27 roster re-audit — October 18, 2026

**Purpose:** Re-run October 13 national ESPN D-I season roster identity check using the same season-specific `hoopR::espn_mbb_team_season_roster()` function. **Research-only**: not a Portal import, no Netlify deployment, no model updates.

## National readiness
| Signal | October 13 | October 18 | Change |
|---|---:|---:|---:|
| All D-I schools | 365 | 365 | 0 |
| At least one newly listed ESPN athlete ID | 133 | **320** | **+187** |
| Zero newly listed ESPN athlete IDs | 232 | **45** | **-187** |
| Share showing at least one new ID | 36.4% | **87.7%** | **+51.2 percentage points** |

New October 18 details: **312** teams have at least five newly listed ESPN athlete IDs and at least 10 current listed players; **8** have only 1–4 new IDs; **45** have none. **Three** are exactly the same athlete-ID roster; the other **42** show no newcomer but have only removed players. **All 365** team fetches succeeded; none lacks a 2027 roster response. ESPN currently lists **5,426** unique athletes in 2027 across 365 teams, with no athlete ID duplicated across 2027 teams. Comparisons against previous 2026 team season rosters identify **3,181 new team-ID memberships**, representing **1,709 player IDs absent from *any* team’s 2026 ESPN season-roster set**. Neither number should be called an official count of truly new D-I freshmen or transfers; 2026 season-roster data contain artifacts.

### Changed examples
| School | Oct 13 2027 | Oct 18 2027 | 2026-to-2027 returning IDs | New school IDs |
|---|---:|---:|---:|---:|
| Kansas State | 14 | 14 | 1 | 13 |
| Cal State Northridge (CSUN) | 16 (no new IDs) | 16 | 5 | **11** |
| Montana | 12 (no new IDs) | 14 | 5 | **9** |
| Wisconsin | previously no new IDs | 15 | 7 | **8** |
| Washington | previously no new IDs | 15 | 6 | **9** |
| Butler | previously no new IDs | 15 | 5 | **10** |
| Creighton | previously no new IDs | 15 | 6 | **9** |
| St. John's | previously no new IDs | 16 | 6 | **10** |

**Caution:** Kansas State still has 13 new school IDs because it was already refreshed, but the broader ESPN rollout has moved substantially. Today's 2027 roster cardinalities do NOT guarantee every school has finalized its complete roster.

## The 45 schools still showing zero new ESPN player IDs
All 45 had 2026 and 2027 season roster responses; 3 exact repeats and 42 trimmed subsets. No new IDs often signals stale/partial data.

| School | Prior roster IDs | Current roster IDs | New IDs |
|---|---:|---:|---:|
| Alabama A&M Bulldogs | 21 | 15 | 0 |
| Alabama State Hornets | 17 | 13 | 0 |
| Alcorn State Braves | 13 | 11 | 0 |
| Arkansas-Pine Bluff Golden Lions | 16 | 13 | 0 |
| Bethune-Cookman Wildcats | 16 | 16 | 0 |
| Cal State Fullerton Titans | 19 | 14 | 0 |
| Chattanooga Mocs | 17 | 13 | 0 |
| Chicago State Cougars | 18 | 16 | 0 |
| Florida A&M Rattlers | 16 | 14 | 0 |
| Grambling Tigers | 28 | 13 | 0 |
| Jackson State Tigers | 16 | 15 | 0 |
| Jacksonville Dolphins | 18 | 14 | 0 |
| Kansas City Roos | 15 | 12 | 0 |
| LSU New Orleans Privateers | 17 | 10 | 0 |
| McNeese Cowboys | 20 | 12 | 0 |
| Mississippi Valley State Delta Devils | 17 | 16 | 0 |
| Morehead State Eagles | 17 | 13 | 0 |
| Nicholls Colonels | 15 | 13 | 0 |
| North Dakota State Bison | 14 | 7 | 0 |
| Northwestern State Demons | 14 | 10 | 0 |
| Omaha Mavericks | 17 | 14 | 0 |
| Oral Roberts Golden Eagles | 14 | 11 | 0 |
| Prairie View A&M Panthers | 29 | 15 | 0 |
| SE Louisiana Lions | 15 | 13 | 0 |
| SIU Edwardsville Cougars | 15 | 14 | 0 |
| Samford Bulldogs | 18 | 14 | 0 |
| South Dakota Coyotes | 19 | 12 | 0 |
| South Dakota State Jackrabbits | 14 | 11 | 0 |
| Southeast Missouri State Redhawks | 14 | 12 | 0 |
| Southern Illinois Salukis | 15 | 11 | 0 |
| Southern Indiana Screaming Eagles | 16 | 13 | 0 |
| Southern Jaguars | 32 | 16 | 0 |
| St. Thomas Tommies | 16 | 10 | 0 |
| Stephen F. Austin Lumberjacks | 16 | 11 | 0 |
| Tennessee State Tigers | 16 | 11 | 0 |
| Tennessee Tech Golden Eagles | 16 | 13 | 0 |
| Texas A&M-Corpus Christi Islanders | 17 | 17 | 0 |
| The Citadel Bulldogs | 18 | 14 | 0 |
| UNC Greensboro Spartans | 15 | 7 | 0 |
| UT Martin Skyhawks | 19 | 12 | 0 |
| UT Rio Grande Valley Vaqueros | 16 | 9 | 0 |
| VMI Keydets | 15 | 10 | 0 |
| Western Carolina Catamounts | 34 | 10 | 0 |
| Western Illinois Leathernecks | 15 | 15 | 0 |
| Wofford Terriers | 15 | 9 | 0 |

## The eight schools with only 1–4 new athlete IDs
These may or may not be complete, but need targeted review.

| School | Prior roster IDs | Current roster IDs | New IDs |
|---|---:|---:|---:|
| American University Eagles | 20 | 17 | 3 |
| Cal Poly Mustangs | 16 | 15 | 2 |
| Colgate Raiders | 16 | 14 | 3 |
| Florida Gators | 17 | 15 | 4 |
| Howard Bison | 17 | 15 | 4 |
| Iowa Hawkeyes | 16 | 14 | 4 |
| Presbyterian Blue Hose | 18 | 15 | 4 |
| Princeton Tigers | 18 | 20 | 4 |

## Particularly short 2027 rosters
| School | Current roster IDs | New IDs |
|---|---:|---:|
| North Dakota State Bison | 7 | 0 |
| UNC Greensboro Spartans | 7 | 0 |
| UT Rio Grande Valley Vaqueros | 9 | 0 |
| Wofford Terriers | 9 | 0 |

## Interpretation and safe next steps
1. **Do not equate an updated roster with a complete roster.** Same season-specific ESPN core roster endpoint as earlier. Unexpected historically contaminated ESPN 2026 season rosters can distort 'departed' comparisons.
2. **Do not wholesale import 2027 rosters yet**: 45 schools show no newcomers; short and partial rosters remain. Keep national data unchanged while investigating high-confidence cohorts.
3. Re-audit weekly or every few days approaching tipoff, and add verification of names, position, height, team, cross-team athlete-ID uniqueness, and historic identity continuity on candidate import. Historical ESPN athlete IDs alone cannot prove eligibility.
4. hoopR remains allowed as the ESPN collection helper; no third-party lineup/RAPM dependencies should be involved. No need to create an independent roster web scraper.
5. No live Portal, Netlify, Sheets, staff data, or model output changed.

## Raw verified research results
- `team_roster_status_20261018.csv`: 365 team-level comparison rows and exact status.
- `season_roster_ids_20261018.csv`: research-only ESPN roster team memberships for both seasons.
- `national_summary_20261018.json`: machine-readable all-teams overview.
- Same research branch script: `scripts/research_roster_2027_reaudit.R`.
