# November 2026 Portal NIL opening-week release gates

**Latest decision:** Portal website V7.72 + GitHub NIL v3 are the MATCHED release pair.
**Status:** complete offline and secret-backed GitHub shadow validation; **do not merge until one final Netlify TEST check**.

## Locked 2026–27 baseline by ESPN ID

| Source | Identities | Frozen prices |
|---|---:|---|
| Original site V4 prior-season valuations | **3,052** | Original V4 price, with $20K publication floor |
| Existing site freshman ranked/unranked baseline | **1,420** | Original HS rank / previous-team-strength pricing, no invention |
| Combined immutable Stock Watch preseason | **4,472** | Exact union, no duplicate IDs |
| Previously deployed v2 baseline rollback | **3,051** | Exact archived file from 2026-10-24 |

Timo Malovec ESPN ID `5281366` must be present with **$791,196** original V4; this player was missing from the older 3,051-ID frozen file. Frozen 2027 freshmen have explicit `FRESHMAN_HS` provenance, and the site preserves their HS School/HS Production labels.

## Pipeline test results, Oct 27, 2026

- GitHub PR tests: **PASS**, including identity, baseline components, migration fail-closed cases and fourfold movement rejection.
- Full secret-backed NIL preseason shadow: **PASS**. Output **11,877** estimates; all **4,472** frozen anchors match, 0 false preseason Stock Watch days; model JSON **2,874,870 bytes**.
- Genuine pipeline synthetic season replay (in isolated runner only): **PASS**. Two official-shaped player games -> one `UPDATED` returning player -> exactly one dated Stock Watch snapshot -> all 1,420 freshmen retained at original baseline.
- See https://github.com/BryceHaase8/kstate-mbb-data-feed/actions/runs/40547914495
- Private fitted model only decrypted in runner; no GitHub `main` push or synthetic/game data publication.

## One Netlify TEST deployment remaining

1. Upload **V7.72** extracted website root to the existing Netlify TEST project, with its `netlify.toml` and `netlify/functions` intact. Do not use V7.71.
2. Verify V4 prices including Timo Malovec, Scharnowski and Jenkins; also one 2026 ranked recruit and one unranked first-year estimate.
3. Verify Stock Watch safely says awaiting V4 migration / first games while GitHub `main` still publishes v2. Gainers and losers are legitimately empty.
4. Verify Google Sheets agents, board, saved notes, Games/Teams, 2027 roster, game logs and player profiles still behave correctly in the test environment; make no sheet schema changes.
5. **After** passing test, deploy the identical V7.72 ZIP to production FIRST; only then merge this PR to turn on GitHub v3. Verify live JSON release, same 4,472 preseason values, first daily update and Stock Watch. Roll back rather than mixing model versions.

## Clear limitations

- Freshmen now have their **own preserved starting prices and history** when games arrive, but lack a validated college-season *relative* reference before playing. We intentionally prevent their open-market values jumping after a few games from an unrelated absolute model price. Calibrate rookie update policy after reliable actual data.
- The website's 2027 shots, on/off, and positions pages can consume published feeds, but the corresponding season PBP publishing jobs remain incomplete. Missing data should be displayed as unavailable, never fabricated.
- No direct access to Netlify deployment or live staff Google Sheets test was used in this project pass.
