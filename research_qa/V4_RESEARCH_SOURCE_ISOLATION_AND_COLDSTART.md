# V4 research boundary, source independence, and newcomer QA
2026-10-18. **Research-only branch.** Do NOT merge into `main` or deploy to Netlify.

## Hard architecture contract

LIVE/DURING-SEASON MODEL INPUT:
- Only **our own collector's** ESPN response snapshots, box scores, roster IDs, and PBP; local GitHub-stored historical player stats and frozen model coefficients.
- Own code must reconstruct possession/lineup outcomes; no `load_ncaa_mbb_rapm`, `load_ncaa_mbb_lineups`, or SportsDataverse season-time refresh.
- The score/forecast function must work when external NCAA release URLs are blocked or no historical RAPM exists for the player.
- **External NCAA RAPM is research-only**: manually download 2023/24/25 archives, compare to *following-season* independently available ESPN data, discard raw archive and store only aggregated QA.
- Torvik data are historical offline model targets/benchmarks, not an online runtime feed.
- Model training and independent out-of-sample validation must be reproducible without re-downloading archives once source snapshots have been approved.

**IMPORTANT VERIFIED CURRENT DEPENDENCY:** Production `main/scripts/daily_update.R` currently invokes `hoopR::load_mbb_player_box`, `hoopR::espn_mbb_season_group_children` and `hoopR::espn_mbb_season_group_teams`. It persists our own derived data but does NOT yet independently query ESPN without hoopR. Do not claim the final independence goal is complete. Migrating this to a tested owned ESPN collector without changing the existing CSV/JSON schema must be a separate gated project before next season.

**IMPORTANT VERIFIED CURRENT ROSTER GAP:** `daily_update.R` filters to `played` box-score rows, and does NOT load all roster-only players. A future roster ingest must add players with zero games to the canonical ID registry before the first game, while leaving current-season box observations missing and impact unscored.

## Historical archive RAPM validation

- Public SportsDataverse `ncaa_mbb_rapm` is **league-wide**; `ncaa_mbb_rapm_within_team` is a distinct estimand and must not be substituted.
- External archive contains NCAA `player_id` and `person_id` (not ESPN athlete ID), `player`, `team`, `orapm`, `drapm`, `rapm_net`, and source possession exposures.
- Real archive 2025 `player` data e.g. `THOMAS.HAUGH` was confirmed to be **FIRST.LAST**, in contrast with misleading documentation saying LAST.FIRST. Parsing reversed names matched essentially no one; corrected and retested.
- Join is research-only, conservative: same season, unique normalized full name on each side **and** school-prefix agreement. No fuzzy auto-match, no identity merges.
- 2023: 3,933 NCAA-ESPN historical unique-name + school matches; 2024: 3,907; 2025: 3,959. About 20–22% do not meet join rules; missing data are not silently guessed.
- Training historical returning rotation cohorts from 2023→24 and 2024→25 had 2,955 matched observations; fully held-out 2025→26 had 1,325.
- Baseline uses source-year box score, observed current-level BPM estimate, and **previously known source-year** originating/destination-program strengths (no following-year strength leakage). `Ridge(alpha=100)` applied identically with and without source-year archived RAPM.
- 2026 target is a frozen *next-season ESPN-derived estimated BPM proxy*. This is NOT true Torvik BPM, and not on-court true impact.
- Holdout MAE: baseline 2.0338; plus archived RAPM 2.0324. Difference **+0.0014** BPM; bootstrap 95% interval **[-0.0017, +0.0046]** overlaps zero. Spearman 0.5583 vs 0.5590.
- Conclusion: No demonstrated incremental predictive value from this particular historical RAPM addition. This is not evidence RAPM is universally useless; strongly confounded by lineup reconstructors' bias, observed-player selection and target measurement.
- No production RAPM weights changed.

## New player and roster-only contracts

`scripts/v4_coldstart_contract.py` scores from **own ESR/ESPN season box rows** and a frozen coefficient file; optional own-roster input can add players with **zero** games. It has **no** network access and no historical RAPM import. No previous-season history is required.

Tests pass with 1,250 first-seen ESPN IDs plus 250 roster-only IDs = **1,500** distinct newcomers:
- 650 unscored for insufficient observed games/minutes (including 250 roster-only).
- 400 provisional, no established ranking.
- 450 established (>=10 GP, >=300 total minutes).
- Duplicate ESPN IDs and missing-season inputs fail closed.
- No constructed zero-BPM for no-data players, and no reconstructed RAPM fabricated for newcomers.

Thresholds/shrinkage are ONLY **provisional implementation safety rules**, not validated forecast probabilities. Tune on chronologically held-out freshman cohorts before considering deployment. Players without ESPN IDs need a separate private temporary portal ID crosswalk with explicit verified ESPN-ID attachment; NEVER merge on names alone.

## Production readiness gates (not yet passed)

1. Direct owned ESPN collectors for schedule, roster, player box, and PBP, with contract tests and fallback snapshots. No hoopR or external NCAA calls in live build.
2. Identity registry has safe union of roster-only + player-box players, correct transfer/renaming transitions, and 1000+ newcomer stress tests.
3. Own lineup inference audited using official player minutes, score continuity and five-player constraints for multiple historical years. Do not infer RAPM on unverified lineups.
4. Independently validate **future-year** Big 12 translation/role models for successful and failed transfers, not just rotation survivors.
5. Refit regularization and luck models only after verified own-possession coverage and chronological input tests.
6. No merge to `main` and no Netlify build until independent collector and quality gates are verified.

Files: `scripts/v4_archive_rapm_ablation.py`, `scripts/v4_coldstart_contract.py`,
`tests/test_v4_coldstart_1250.py`, `tests/test_v4_archive_identity.py`,
`research_qa/v4_archive_rapm_predictiveness.json`.
