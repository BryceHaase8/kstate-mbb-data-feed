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
public/index.html
.github/workflows/daily-update.yml
```

## What the scheduled job does

Every morning at **6:17 AM America/Chicago**:

1. Determine the likely current NCAA season.
2. Pull that season's `hoopR` ESPN player-box data.
3. Get ESPN's Division I team universe.
4. Remove non-D-I team rows.
5. Recalculate clean player-season basic stats.
6. Write `public/portal_factual_data.json`.
7. Publish the `public/` folder to GitHub Pages.

GitHub scheduled workflows can use an IANA timezone, so the schedule follows Central Time/DST.

## First setup

1. Create a **public** GitHub repository.
2. Upload the contents of this folder to the repository root.
3. In GitHub, open **Settings → Pages**.
4. Under **Build and deployment → Source**, choose **GitHub Actions**.
5. Open **Actions → Update basketball factual feed**.
6. Choose **Run workflow**.
7. For the first test, enter `2026` as the optional season override.
8. Wait for both the `build` and `deploy` jobs to finish successfully.
9. Open the GitHub Pages URL shown by the deployment.

The JSON URL will be:

```text
https://YOUR-GITHUB-USERNAME.github.io/YOUR-REPOSITORY-NAME/portal_factual_data.json
```

Do not point the production Portal at the URL yet. Use the separate Netlify test site first.

## Season behavior

Without an override, `daily_update.R` calculates the likely NCAA ending year:
- Jul–Dec 2026 → 2027
- Jan–Jun 2027 → 2027

If that season has no player-box data yet, it falls back one year.

Once 2026–27 games begin appearing in hoopR, the automatic job will begin publishing 2027 data without needing a site redeploy.

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

The script does not touch Netlify or the Google Sheet.

If the remote feed is unavailable, the Portal test build is designed to fall back to its bundled factual data / existing production player fields.
