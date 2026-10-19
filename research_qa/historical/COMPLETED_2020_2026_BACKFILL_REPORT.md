# Seven-season ESPN backfill — completed and independently verified

**Date:** 2026-10-19 UTC  
**Research branch:** `historical-2020-2026-box-gamelogs-pbp-research`  
**Production main / Netlify / Staff data:** Unchanged.

## Final results

| NCAA ending year | Season | D-I players | Games | Player-game records | Selected ESPN PBP games | Play events |
|---:|---|---:|---:|---:|---:|---:|
| 2020 | 2019–20 | 4,796 | 5,766 | 109,685 | 16/16 | 5,046 |
| 2021 | 2020–21 | 5,020 | 4,285 | 83,064 | 16/16 | 5,314 |
| 2022 | 2021–22 | 5,090 | 5,965 | 114,125 | 16/16 | 5,232 |
| 2023 | 2022–23 | 5,102 | 6,221 | 118,870 | 23/24 | 7,640 |
| 2024 | 2023–24 | 5,063 | 6,241 | 119,332 | 23/24 | 7,606 |
| 2025 | 2024–25 | 5,119 | 6,290 | 120,616 | 40/40 | 14,124 |
| 2026 | 2025–26 | 5,019 | 6,300 | 120,412 | 40/40 | 18,601 |
| **Total** | **7 seasons** | **35,209 player-seasons** | **41,068** | **786,104** | **174/176** | **63,563** |

## Independent QA outcome: PASS

A separate GitHub Actions verification (not the collector itself) compared stored season totals with independently re-aggregated player-game records by ESPN athlete ID and season-team:
- **Seven of seven** annual archives present.
- **Zero** duplicate `(game_id, team_id, athlete_id)` player-game keys.
- **Zero** duplicate `(season, athlete_id)` season-summary keys.
- **Zero** mismatches between the aggregated game logs and stored season totals for games played, points, minutes and field-goal attempts.
- **Every** archived 2023, 2024, 2025 and 2026 player-season matched the existing main repository by ESPN athlete ID (all 20,303 rows), with **zero** differences across GP, minutes, points, FGM, FGA, assists, rebounds, 3PM, and 3PA.
- The 2019–20, 2020–21 and 2021–22 season totals add **14,906 historical player-season records** absent from the current main feed.

Historical and game-level data are stored as per-season compressed CSVs in `research_data/historical/`. This makes game logs available for future per-player fetch without adding every single game to the homepage payload.

## PBP is deliberately sampled and not an RAPM result
- One 2023 game and one 2024 game lacked usable PBP; their exact ESPN game IDs are recorded in the annual PBP manifests.
- Most selected games have no missing text; 2024 has three and 2025 has eleven blank event descriptions across their annual samples.
- No sample has been validated for period starters, substitutions, official player minutes, five-on-five integrity, or lineup continuity.
- **No third-party lineup or RAPM was used. No new RAPM estimates are claimed.**

## Next step
1. Safely promote the validated 2019–22 season summaries through a separately reviewed migration, updating `FIRST_SEASON` and schema contracts so the nightly job never discards historical rows.
2. Build the 2026–27 season-specific roster importer, matching by ESPN athlete ID and preserving scouting notes and manual 0–5 eligibility overrides; keep uncertain identities pending.
3. Merge verified roster-only and game-playing athlete records into one player universe. Allow eligible-only filtering by default while preserving 0-year players.
4. Wire Game Logs to separate archived season files, fetched only when player details are opened.
5. Keep the PBP sample as raw input for independent lineup reconstruction research; expand coverage only after we can verify five-man lineups against official minutes.

## Evidence
- `research_qa/historical/full_manifest.json` (full research collector result)
- `research_qa/historical/verification_2020_2026.json` (independent validation)
- `research_qa/historical/box_qa_YYYY.json` and `pbp_qa_YYYY.json` (season-level traceability)
- `.github/workflows/historical-2020-2026-backfill.yml`
- `.github/workflows/historical-archive-verify.yml`
