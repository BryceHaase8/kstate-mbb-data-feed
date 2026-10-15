# College Basketball Factual Data Feed

This repository is the **public factual-data layer** for the Portal.

It intentionally contains **no private Portal information**:
- no staff notes
- no ratings/evaluations
- no board rank/order
- no colors/categories
- no NIL intel
- no agents
- no indication of whether a player is on the internal Portal board

The public JSON contains ordinary NCAA Division I men's basketball factual data keyed by ESPN athlete ID.

## Files

```text
scripts/daily_update.R
scripts/build_public_factual_json.R
data/current_player_season_stats.csv
public/portal_factual_data.json
.github/workflows/daily-update.yml
```

## Live JSON

The Portal can read the current factual feed directly from the repository:

```text
https://raw.githubusercontent.com/BryceHaase8/kstate-mbb-data-feed/main/public/portal_factual_data.json
```

No GitHub Pages setup is required.

## What the scheduled job does

Every morning at **6:17 AM America/Chicago**:

1. Determine the likely current NCAA season.
2. Pull that season's `hoopR` ESPN player-box data.
3. Get ESPN's Division I team universe.
4. Remove non-D-I team rows.
5. Recalculate clean player-season basic stats.
6. Write `data/current_player_season_stats.csv`.
7. Write `public/portal_factual_data.json`.
8. Commit those refreshed factual files back to this repository only when they changed.

The scheduled workflow follows Central Time/DST.

The workflow also runs when the updater scripts or workflow definition change, which lets us test infrastructure changes without touching the Portal.

## Season behavior

Without an override, `daily_update.R` calculates the likely NCAA ending year:
- Jul–Dec 2026 → 2027
- Jan–Jun 2027 → 2027

If that season has no player-box data yet, it falls back one year.

The production Portal is **not** connected yet. The separate Netlify test site should be used first.

## Public JSON contract

Top level:

```json
{
  "schemaVersion": 1,
  "generatedAt": "...",
  "season": 2026,
  "seasonLabel": "2025-26",
  "playerCount": 5019,
  "scope": "NCAA Division I men's basketball factual data only",
  "players": {
    "ESPN_ATHLETE_ID": { "...": "..." }
  }
}
```

The Portal joins this feed to its private player records using ESPN athlete ID.

## Safety behavior

The workflow does not touch Netlify or the Google Sheet.

If the remote feed is unavailable, the Portal test build is designed to fall back to its bundled factual data / existing production player fields.
