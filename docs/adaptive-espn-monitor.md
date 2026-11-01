# Adaptive ESPN game refresh (2026–27)

This changes **only** the GitHub data-feed repository. No Netlify deployment, Portal
website code, staff Google Sheet, frozen NIL opening baseline, or Stock Watch
historical date is modified by the monitor.

## What runs
- **Lightweight monitor:** every 15 minutes at 11:00 AM–2:45 AM Central,
  November–April. Hosted GitHub Actions may delay schedule triggers.
- **Guaranteed full runs:** unchanged at 2:17 AM, 5:17 AM, and 12:17 PM Central
  during November–April; offseason still 6:17 AM daily.
- **Adaptive full runs:** requested only after a verified completed ESPN game is
  missing from published 2027 game logs, an official final score changes, or
  sampled ESPN player box statistics differ from published verified logs.
- **Correction scan:** samples up to 6 recently finished game summaries each
  check, rotating through the last three calendar dates. Older corrections
  are still caught by the guaranteed full runs.

## Safety
1. The monitor reads only ESPN public scoreboards/summaries and the already
   published game-log shards; it NEVER writes player data or NIL prices.
2. The existing full workflow remains the *only* publisher, including the
   original factual QA, optional isolated advanced analytics and guarded NIL
   validation. Failures leave previous validated outputs in place.
3. An in-flight full run prevents adaptive dispatch; a previous dispatch starts
   a 45-minute cooldown to reduce repeated attempts while data propagates.
4. Missing or malformed published shard coverage fails closed. A completely
   absent manifest is valid until the first official 2026–27 player box data.
5. Active full runs are never canceled by a new request
   (`cancel-in-progress: false`); GitHub may replace an obsolete pending run.
6. Monitoring requires GitHub Actions `actions:write` in the checker workflow,
   but uses only a short-lived GitHub Actions token.
7. Failures in the read-only checker cannot alter the published data.

## Logs to monitor
GitHub Actions > **Monitor ESPN final games (lightweight)**:
- `NO CHANGE`: no full refresh needed.
- `DRY RUN`: no dispatch requested.
- `DISPATCHED`: a full refresh was queued.
- `Dispatch gate`: in-flight run or cooldown suppressed a redundant refresh.
- `MONITOR FAILED SAFELY`: scoreboard, GitHub API or schema problem; no publish.

GitHub Actions > **Update basketball factual feed + NIL Stock Watch**:
- Inspect all successful/failed steps separately. The full workflow is
  intentionally the existing verified publisher.

## Validation and tuning
- Unit tests: `python3 -m unittest discover -s tests -p 'test_game_change_monitor.py' -v`
- Before relying on live updates, verify a real ESPN completed game triggers
  one full workflow and its published box appears in the next scan.
- If the source runs lag during peak nights, increase the 45-minute cooldown
  or decrease the number of correction summaries. Do not increase concurrency
  without measuring the longest setup/runtime outliers.
- If ESPN provides partial or corrected stats after more than three days,
  the scheduled complete rebuilds still reconcile the season.

## Boundaries
The monitor does not continuously update live play-by-play or midgame
statistics: it is keyed to completed games and verified player box scores.
It is not an exact 15-minute SLA; ESPN and GitHub scheduled jobs may lag.
