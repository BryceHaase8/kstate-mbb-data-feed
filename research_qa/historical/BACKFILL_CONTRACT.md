# Historical ESPN basketball archive — research-only contract

## Objective
Backfill NCAA men's D-I **2019–20 through 2025–26** factual data as one coordinated, one-time process, before handling 2026–27 rosters.

## Three distinct outputs
- `research_data/historical/season_totals/player_season_YYYY.csv.gz`: D-I player-season statistics computed with the **existing** Portal factual feed aggregator, even for 2019–20 through 2021–22.
- `research_data/historical/game_logs/player_game_logs_YYYY.csv.gz`: D-I player-game box records with ESPN athlete IDs, ESPN game IDs, opponents, dates, scores and shooting totals. Unlike aggregates, this has game-by-game granularity.
- `research_data/historical/selected_pbp/raw_espn_pbp_sample_YYYY.csv.gz`: **research sample**, distributed through each season; original ESPN event description, chronological fields and substitutions when available. These are NOT validated lineups and NOT league-wide PBP. Season samples are 16 games (2020–22), 24 games (2023–24), and 40 games (2025–26), subject to missing event data. Do not replace missing games with made-up event records.

## Provider and independence
hoopR downloads ESPN player-game boxes and raw per-game play events. We own the D-I filtering, player-season aggregation, quality checks, storage, and future lineup reconstruction / possession classification / RAPM. **Never use a purported hoopR lineup or RAPM as an in-season dependency.** The modern `hoopR::load_mbb_pbp()` endpoint is explicitly a **shot dataset**, and so is NOT an adequate input to our full lineup reconstruction; this archive uses `hoopR::espn_mbb_pbp(game_id)` instead.

## Safety
1. Entirely isolated to branch `historical-2020-2026-box-gamelogs-pbp-research`. The daily production branch, Netlify Portal and Google Sheets remain untouched.
2. Raw and archived research files must remain outside `public/portal_factual_data.json`. No homepage needs raw PBP.
3. Preserve both the original ESPN athlete ID and game/team IDs to avoid matching athletes by name alone.
4. `research_qa/historical/box_qa_YYYY.json` and `pbp_qa_YYYY.json` accompany each archive to flag coverage.
5. Player-season summaries currently discard second team entry when a player played for multiple schools during one season, exactly as the existing daily aggregator does. This should be separately audited before promotion.
6. A roster-only player has no game log. **Do not drop roster-only new players** during the later 2026–27 roster integration. Unknown eligibility must not be coded as 0.
7. An archived PBP game does **not** become RAPM-ready until five-on-five lineup reconstruction meets period-starter checks, full official minute reconciliation, valid substitution chronology, and possession count/replay validation. Prior independent lineup coverage failed this standard. Treat all historical PBP as raw research material.
8. Once research QA succeeds, later work can promote 2019–22 season summaries into the main public factual feed using a planned migration, and expose game logs through a separate endpoint. No auto-deployment is part of this workflow.

## Re-run and reproducibility
The workflow is manual or research-code-push-triggered. It can be restricted to one season using `BACKFILL_FIRST_SEASON`/`BACKFILL_LAST_SEASON`. Pilot mode selects 2022 and only 3 PBP games. File names are deterministic by season. Source releases may change, so QA must be compared against previous historical results before overwriting a validated archive.

## Release gates
- All seven player-season and game-log archives present with plausible coverage.
- Per-game key `(game_id, team_id, athlete_id)` unique.
- Player-season key `(season, athlete_id)` unique (existing production behavior).
- Each selected PBP cohort's successful/missing games and event counts clearly reported.
- Any differences against existing 2023–26 production seasonal aggregates investigated before merge.
- No change to Portal homepage, private scout or model files, production daily collector, or live data until separately audited.

Note: historical PBP here is deliberately **selective**, not complete league-wide multi-season event coverage. When high-quality lineup reconstruction is demonstrated, expanding its coverage is a future modeling step.
