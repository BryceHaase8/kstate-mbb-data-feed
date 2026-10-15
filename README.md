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

## Live feed

```text
https://raw.githubusercontent.com/BryceHaase8/kstate-mbb-data-feed/main/public/portal_factual_data.json
```

The current feed preserves the full canonical history beginning with:

- 2022-23
- 2023-24
- 2024-25
- 2025-26

Current verified build:
- 20,303 player-season rows
- 10,476 unique ESPN athlete IDs
- 5,019 players in 2025-26

## Daily update design

The repository does **not** redownload every historical season each morning.

On the first multi-season run, the workflow bootstrapped missing historical seasons once and stored them in:

```text
data/current_player_season_stats.csv
```

The filename is retained for compatibility even though it now stores multiple seasons.

On normal future runs:

1. Determine the active NCAA season.
2. Download/rebuild only the active season.
3. Preserve all older stored seasons.
4. Replace the active-season rows.
5. Rebuild `public/portal_factual_data.json`.
6. Commit the refreshed factual files only when they changed.

When a new season begins, the prior season automatically becomes preserved history.

## Public JSON shape

```json
{
  "schemaVersion": 2,
  "generatedAt": "...",
  "latestSeason": 2026,
  "seasonCount": 4,
  "seasons": [2023, 2024, 2025, 2026],
  "playerSeasonCount": 20303,
  "playerCount": 10476,
  "players": {
    "ESPN_ATHLETE_ID": {
      "espnAthleteId": "ESPN_ATHLETE_ID",
      "latest": { "...": "most recent season record" },
      "seasons": [
        { "...": "season record" }
      ]
    }
  }
}
```

The Portal joins this public feed to its private player records using ESPN athlete ID.

## Safety behavior

The GitHub workflow does not touch Netlify or the Google Sheet.

The Netlify Portal has a bundled factual snapshot as a fallback. If the remote feed is unavailable, staff data and the existing Portal remain usable.


## Research team rankings (annual)

The staff Research interface uses final-season Bart Torvik team ranks and season-specific
conferences supplied by staff CSV exports and bundled privately with the Netlify Research
build. The rankings are refreshed manually **once per offseason**; they are **not**
collected, recomputed, or redistributed by this public daily GitHub workflow.
The former ESPN-derived `public/research_team_context.json` is retained as a legacy
file only and is no longer refreshed or used by the updated Research page.
