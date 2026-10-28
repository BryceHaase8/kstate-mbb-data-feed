# 2026–27 advanced analytics publishing — opening-week readiness

This release hardens the existing (already scheduled) GitHub data pipeline. It is
**not** a Netlify deploy and it does **not** change the 2026–27 NIL estimator,
immutable preseason anchors, or ESPN game logs.

## Input and scope

- ESPN D-I game-level boxes via hoopR: `data/advanced_2027_player_box.csv.gz`.
- ESPN/hoopR per-game play-by-play: `data/advanced_2027_pbp/games/<ESPN game ID>.csv.gz`.
- Verified roster ID/position/size: `data/roster_2027_advanced.json`.
- `scripts/daily_update.R` collects the new data after official game boxes;
  `.github/workflows/daily-update.yml` executes the new Python QA + publisher,
  then stages all verified-game caches and public shards.
- Only real 2026–27, two-Division-I-team games qualify. No historical PBP,
  synthetic examples or false dates are published as current-season outcomes.

## Exact URL contracts

- `public/portal_shots_2027/manifest.json`,
  `shots_000.json` through `shots_127.json` (9-field ESPN-ID rows).
- `public/portal_onoff_2027/manifest.json`,
  `onoff_000.json` through `onoff_127.json` (games, on/off minutes,
  verified box minutes, descriptive offense/defense shooting/four factors).
- `public/portal_positions_2027/manifest.json`,
  `positions_000.json` through `positions_127.json` (PG/SG/SF/PF/C
  estimated role minutes over verified five-player lineup stints).

All three are already referenced by the V7.74 website's public GitHub URLs.
No client-side URL or Netlify setting change is required.

## Fail-closed and interpretation

- A shot-game is accepted only if **every player's** FGA, FGM, 3PA, and 3PM
  match the same game's official ESPN box and every shot has a valid location
  and ESPN athlete/team ID. Current-season shot samples are explicitly marked
  **partial** in their manifest.
- Coordinate orientation is validated against ESPN's own shot-distance text.
  The real archived 2025–26 `hoopR::espn_mbb_pbp(401856563)` probe confirmed
  the legacy lengthwise frame (coordinate x about -44..43, y about -23..24).
  New/ambiguous coordinate formats are *rejected*, never quietly reversed.
- On/Off requires exactly five verified players per team between time-stamped
  substitutions. Both paired-ID and one-athlete "subbing in/out" records are
  supported; reconstructed minutes must reconcile with official box minutes.
- Defense-related rebounds/steals/blocks/fouls are assigned to the correct
  on/off defensive side; shot zones come from the very same validated PBP.
  The results are **descriptive, not RAPM, adjusted impact, or causal effects**.
- Positions are role estimates from the five simultaneously verified athletes
  and their ESPN-listed role/height. They are **not tracking-measured positions**.
- No verified 2026–27 games means no advanced manifests or synthetic player
  rows. A missing/partial PBP game cannot block the official ESPN box refresh
  or NIL/Stock Watch.
- Accepted games are cached individually in
  `data/advanced_2027_verified_games`; fully verified records are immutable.
  Later data repairs can add previously missing lineup coverage, without
  destroying accepted shots. The public daily commit includes the cache.
- The first real games require coverage review against the published QA
  manifest, particularly skipped-game reasons and minutes disagreements.
  **A missing game is never silently presented as a zero-stat performance.**

## Verification

- `python -m unittest discover -s tests -p 'test_build_2027_advanced.py'`
- `python -m unittest discover -s tests -p 'test_advanced_2027_publisher.py'`
- `python scripts/publish_2027_advanced.py` in the preseason checkout
  must generate **no** fabricated 2027 advanced manifests.
- Real archived ESPN schema was probed in GitHub Actions and passed;
  an on-demand probe remains at
  `.github/workflows/espn-advanced-archive-probe.yml`.

## Remaining launch gate

2026–27 games have not yet produced live published PBP. Once the first verified
ESPN games arrive, inspect the advanced manifest QA totals, player and team
sample coverage and the website tabs. This is a production **first-real-game
validation**, not a justification to fabricate values now.
