# Seven-year historical migration + 2026–27 roster staging — October 19, 2026

## Verified

All work is on the research staging branch. **Production `main` and live Netlify Portal are unchanged.**

| Check | Result |
|---|---:|
| Canonical archive seasons | 2019–20 through 2025–26 |
| Historical player-season rows | **35,209** |
| ESPN athlete IDs in historical archive | **15,199** |
| Added 2019–22 player-season rows | **14,906** |
| Existing 2023–26 records changed | **0** |
| Public feed schema | v2 unchanged |
| Public feed season scope | 2022–23 through 2025–26 unchanged |
| Public feed rows / IDs | **20,303 / 10,476** unchanged |
| Current 2026–27 roster season-specific athlete IDs | **5,456** |
| Division I teams | **365** |
| IDs linked to full seven-year game-stat archive | **3,416** |
| IDs not found in historical box archive | **2,040** |
| Names unresolved | **0** |
| Site-v2 bio mismatches | **1** |
| Duplicate 2027 ESPN athlete IDs across teams | **0** |

## Roster completeness signal

- **331** team rosters have at least one new ESPN athlete ID, >=10 listed players and >=95% bio coverage (preliminary, not verified complete).
- **30** still have no new IDs compared with last year.
- **3** remain unusually short: UNC Greensboro (7), UTRGV (9), Wofford (9).
- **1** has insufficient current bio match: Denver (14 of 15 season IDs match current roster bios).
- All 365 team-fetch requests completed.

**Do not treat 331 plausible updates as 331 independently verified final rosters.** Remaining exceptions should be reviewed, and an updated full-season roster import should run closer to tipoff.

## Implementation

1. `scripts/stage_historical_history.R`: reconciles old compressed season totals with the existing production 2023–26 dataset, byte-equivalent for the 20,303 existing rows.
2. `scripts/stage_production_history_2020_2026.R`: generates a candidate seven-year canonical CSV in the staging branch, with public JSON kept on its legacy four-year scope.
3. `scripts/daily_update.R` on staging branch: `FIRST_SEASON = 2020`; nightly updater preserves the three older seasons once promoted.
4. `scripts/build_public_factual_json.R` on staging branch: keeps public all-in-one player JSON limited to the existing 2023+ records to avoid expanding an already-large 27MB initial download.
5. `scripts/stage_2027_roster_universe.R`: collects both ESPN core-v2 season-specific memberships and site-v2 player bios via hoopR, joins by exact ESPN athlete IDs and separately checks historical stat identity; no name-based merges.
6. Separate staging outputs: `research_data/staged/current_roster_2027_candidate.json` (approx. 2MB) and `current_roster_2027_identity.csv`, with review flags. No eligibility guesses, NIL estimates or invented statistics.
7. Website V7.4 review ZIP outside GitHub: copies V7.3, adds a **test-only** lazy roster loader without UI style changes. It does not mutate staff notes/evaluations, Board status or eligibility overrides.

## Tests and gates

- Full historical staging workflow: passed.
- All 365 roster source and identity staging workflow: passed.
- Candidate seven-year canonical + unchanged public feed staging workflow: passed.
- JS identity stress test: 5,456 synthetic current roster records, 60 existing matches, 5,396 new players, identity duplication rejection, repeat load idempotence, zero invented eligibility or stats, staff field preservation: passed.
- Browser testing of V7.4: not completed — container Chromium blocks local/file navigation. The actual 2027 roster staging feed therefore still requires an end-to-end browser test.
- Large seven-year canonical file **not** merged to production main; test ZIP **not** deployed to Netlify.

**Next release gate:** verify V7.4 against the actual GitHub roster feed and current Google Sheets eligibility overrides on an isolated test deployment, resolve the 34 roster review teams, and only then promote the data-feed migration and roster importer to main. Keep older historical season details on a lazy endpoint; do not add raw PBP or the full seven-year history to the Players-tab initial payload.
