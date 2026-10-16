# Season-to-date ESPN RAPM — isolated research build

**Do not merge this into the production player-stat feed yet.** This is a tested local prototype and a ready-to-stage standalone daily GitHub Action, using the cumulative active-season data from `hoopR::load_mbb_pbp()` and `hoopR::load_mbb_player_box()`. It does not depend on annual SportsDataverse RAPM releases or Torvik final team ranks.

## What it does
1. Download **only the active NCAA season** in `scripts/rapm_ingest.R`.
2. Reconstruct both teams' five-man lineups using **official first-half starters + PBP substitution events**. Later-period starters are inferred from events and every player-event checked.
3. Verify player minutes against official game boxes (within 1.01 minutes), plus team score and team possession-count reasonableness.
4. Assign possession outcomes, mark ambiguous possessions, and fit heavily regularized offensive and defensive player effects per 100 possessions to accepted games.
5. Write a separate `public/rapm_research_audit.json` on every data-bearing run. Publish a separate `public/rapm_research.json` *only if* basic volume (20 accepted games, 3,000 clean possessions) and coverage (>=40% accepted) gates pass. Never overwrite an existing good rating file on empty-data/error runs.

**Research-only:** a passing run still yields provisional coefficients, **not** validated player rankings. The Portal and V6 Research don't consume either new file. A site deployment is unnecessary for fresh data *once the eventual site integration is approved and implemented*.

## Test evidence
- Local smoke run: 100 previously lineup-verified ESPN games, synthetic official boxes derived from those same validated stints (NOT independent minutes): 98 game candidates, 48 accepted, 6,146 clean possessions, 232 provisional coefficient rows. This is a software integration test, not evidence of accuracy.
- Prior independent verification: 25 ESPN games, 250/250 starting slots and 489/489 player-game minute estimates within 1 minute of *actual* hoopR box scores (Phase 1 audit).
- Current remaining issue: score/FT possession reconciliation excludes many games; ratings cannot yet be used in the outcome probability model.

## Local use
```
Rscript scripts/rapm_ingest.R
OPENBLAS_NUM_THREADS=1 python scripts/rapm_daily.py --season 2027
```
Requires R `hoopR,dplyr,readr` and Python `pandas,numpy,scipy,scikit-learn`.

Test on included synthetic fixture:
```
OPENBLAS_NUM_THREADS=1 python scripts/rapm_daily.py --season 2026 \
  --pbp fixtures/pbp_100_games.csv --box fixtures/box_100_games_SYNTHETIC.csv \
  --output public/rapm_research.json --audit public/rapm_research_audit.json
```

The scheduled GitHub Action runs at 7:47 AM America/Chicago **only after this workflow is added to the default branch**. It remains non-scheduled while isolated on the research branch, per GitHub Actions rules. The daily Portal player-stat workflow remains untouched.
