# Torvik bulk-data resilience — research branch only

## Status (2026-10-17)

No production feed or Portal deployment was modified.

GitHub-hosted Ubuntu Actions currently receives CloudFront HTTP 403 for published Torvik team-results files:
- 2027 JSON and CSV: Python urllib with identifying User-Agent, both 403.
- 2027 JSON and CSV: browser-compatible identifying User-Agent, both 403.
- 2027 JSON: standard curl, 403.
- 2026 historical JSON: standard curl, 403.

This does not identify the precise CloudFront rule. No IP rotation, bypassing the publisher's restrictions, or unapproved mirrors were used.

## Ready

- scripts/torvik_bulk_daily.py is a single-run downloader for the published JSON, with the published CSV as fallback only if the JSON is unavailable or malformed. A 403 stops attempts immediately rather than trying multiple routes.
- Only retry temporary HTTP 408, 429, 5xx, and network errors, using bounded backoff. Never retry HTTP 403.
- Strict validation of the 45-column JSON/CSV schema, team count, ranks, names, and metric ranges. Refuse error-page HTML, duplicate teams, or incomplete data.
- ESPN team ID crosswalk from existing ESPN team directory, with longest school-name matching and match-quality gate. Unmatched schools explicitly recorded.
- Normalized schema-v2 research JSON with AdjOE, AdjDE, AdjEM, season, provider, preseason status, source checksum, ESPN IDs, timestamps.
- Unchanged file -> no rewrite. Failed request with verified cached ratings -> retain cache and write staleness status; failure without a cache -> nonzero exit. Model must distinguish stale from fresh.
- It does not crawl pages or change RAPM coefficients.

## Verified tests

- tests/test_torvik_bulk_resilience.py passed on GitHub Actions with a complete synthetic 365-team JSON and CSV matching the existing ESPN directory.
- Tests covered preseason detection, Kansas State ESPN ID 2306, crosswalk minimum coverage, schema validation, unchanged-source hashing, rejection of malformed content, and keeping the last valid file.
- .github/workflows/torvik-bulk-resilience.yml runs offline tests on research-branch changes and has an optional explicit manual mode live_once.
- The older torvik-json-research-test.yml is superseded.

## Path to an automatic next-season system

1. Verify a publisher-approved bulk-data path. Direct GitHub-hosted requests still fail with 403. Repeating retries alone will not fix it.
2. If a permitted network can access the file, we can run this same script through a secured self-hosted GitHub Actions runner on that network, after verifying allowed usage. Or use a publisher-approved bulk file handoff and ingest the local JSON/CSV fixture.
3. Agree on permission for storing/redistributing Torvik data before publishing full snapshots to any public repository.
4. Once access works, add the daily schedule on the default branch (schedules do not execute on research-only branches), review alerting and snapshot retention, and separately test the team-rating/RAPM model join. No production promotion or automatic scheduled run yet.

Commands:
- Offline unit tests: python tests/test_torvik_bulk_resilience.py
- Validated manual local file: python scripts/torvik_bulk_daily.py --season 2027 --fixture /path/to/2027_team_results.json
- A single live check when access is permitted: python scripts/torvik_bulk_daily.py --season 2027

Do not use synthetic tests to seed a production data cache.
