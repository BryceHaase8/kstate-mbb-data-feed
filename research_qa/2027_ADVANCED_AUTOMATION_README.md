# Automatic 2026–27 advanced ESPN analytics — production gating

**Status:** Implemented and synthetic tests pass in the research branch. **NOT MERGED, NOT LIVE.** No Netlify deployment or extra service is required; the latest Portal V7.73 already points at these exact paths on GitHub `main`.

## What updates when real ESPN games arrive

The existing scheduled `.github/workflows/daily-update.yml` already updates the national ESPN box feed, game logs, NIL prices, and Stock Watch. This branch adds a **separately guarded** step:

1. `scripts/daily_update.R` invokes `scripts/collect_2027_advanced.R` only for 2026–27, using the **same installed hoopR** to retrieve per-game ESPN PBP after a completed game appears in the ESPN player box. It caches each completed game by ESPN ID as `data/advanced_2027_pbp/games/<gameId>.csv.gz`; future runs skip valid already-collected games. A 200-new-game cap bounds per-run API calls and allows backlog catch-up.
2. `scripts/build_2027_advanced.py` runs **after** the factual feed passes validation and independently publishes the existing site-compatible 128-shard formats. The Python builder uses **stdlib only**, no player Torvik data, additional paid provider, or new Netlify Function.
3. All advanced output is committed with the existing GitHub daily update only if its QA step succeeds. Otherwise, ESPN box scores, NIL and Stock Watch continue unaffected.

| GitHub output | What it represents | Validation |
|---|---|---|
| `public/portal_shots_2027/manifest.json`, `shots_000..127.json` | Real ESPN shots, mapped to NCAA half-court coordinates | Exact player/game/team IDs, D-I vs D-I matchup, 2/3-point play type, 75%+ mapped coordinate/FGA coverage relative to ESPN box |
| `public/portal_onoff_2027/manifest.json`, `onoff_000..127.json` | Non-causal descriptive team ON/OFF offense, defense and pace | Per-player substitutions and verified on-court minutes within 2.1 minutes of ESPN player box; games with ambiguous state dropped |
| `public/portal_positions_2027/manifest.json`, `positions_000..127.json` | Estimated PG/SG/SF/PF/C percentages while five players verified on court | Strict five-active-player intervals, exact ESPN athlete IDs, roster size and listed-position priors, minimum verified 10 minutes. Estimates, NOT tracking facts |

The website already uses `PORTAL_SHOTS_2027_BASE`, `PORTAL_ONOFF_2027_BASE`, `PORTAL_POSITIONS_2027_BASE` pointing to these publication paths on GitHub main; **no site-version change is required to consume the new 2027 files**.

## No false availability

- Before the first real verified game there are **no 2027 advanced manifests**; site displays a truthful waiting message.
- ESPN plays missing coordinates are excluded; some games may be omitted from shots.
- Individual ON/OFF does not claim to reconstruct universally complete five-player lineups and does not calculate RAPM.
- Positions are inferred roles, not measured player tracking. Unknown or conflicting lineup intervals are excluded.
- A game may populate shooting charts while its ON/OFF and positions remain unavailable due to missing substitutions or unclear minutes. This is intentional, not a silent default.

## QA / release sequence

1. Research CI: `python -m unittest discover -s tests -p test_build_2027_advanced.py -v` uses a two-half synthetic game, checks all JSON contracts, makes sure empty preseason does not publish, invalid locations are rejected and size priors behave.
2. Existing GitHub PR #5 and V7.73 test site must pass before merging the data-feed integration. This PR is **based on the PR #5 research branch**, not production main.
3. Historical live hoopR schema probe is opt-in only (cold R installs expensive). Actual 2026–27 ESPN game/substitution quality cannot be certified until a real finished game exists.
4. On opening week, verify first new ESPN game ID is cached, published shots match box FGA, verified on/off minutes match official box, positions do not exceed player minutes, and any rejected samples are not shown as complete.
5. Do not treat full-season shot completeness or site Impact V3 recalibration as automatic results of these descriptive feeds. They are separate workflows.

No staff scouting, agents, asking prices, or private compensation records are used or published.
