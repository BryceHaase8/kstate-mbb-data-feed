# V4 NIL and Stock Watch release gates — updated October 27, 2026

**Draft PR #5; no production deployment.** The companion portal website build is V7.71.

## Staged launch files
- `public/stock_watch/preseason_2027.json`: full original site V7.70 frozen V4 baseline, exactly **3,051/3,051** existing ESPN IDs; no older-model fallback among those IDs.
- `public/stock_watch/v4_preseason_2027_candidate.json`: same 3,051 original V4 values; independent release comparison.
- `public/stock_watch/preseason_2027_legacy_2026_10_24.json`: exact earlier v2 baseline, preserved for rollback.
- `public/stock_watch/manifest_2027.json`: V4 baseline migration date 2026-10-27, with **no historical in-season snapshots**.
- No new Torvik player-data feed; V4 is one-time offline frozen input only. Automatic season updates use ESPN-derived stats, historical context and the existing Torvik **team-level** ratings.

## Model/website compatibility
- Engine: `nil-v4-relative-v3-2026-10-27` and `policyVersion=3`.
- The V4 value is the dollar anchor. Auxiliary model's *same-model 2027 reference/current ratio* drives growth/decline, progressively gated by games and minutes.
- Netlify ZIP V7.71 rejects v2 live feeds as stale and any v3 feed whose `preseason` entries differ from the original V4 by even $1.
- The Stock Watch function won't display legacy v2 price changes as V4 movements.
- A special publishing guard permits the single 3,051-ID baseline migration ONLY when both original anchors, empty dated history and valid preseason ESPN facts are present. All later publications use normal strict drift/coverage rules.

## Quality assurance
- Synthetic GitHub PR job ran **11/11 unit tests successfully** after correcting its expected release version; no private model keys were exposed to the test runner.
- Local V7.71 frontend tests passed (old v2 reject, valid v3 accept, single V4 discrepancy reject, missing-ID reject, Stock Watch before/after migration).
- Existing filters, Portal risk, roster functions and agents tests passed. An older legacy test references a development folder absent from this ZIP; full historic test portability is not complete.
- Exact V4 candidate vs site V7.70: **3051 identities and values match**; two original sub-$20K scores use $20K display floor.

## Not yet done / no production merge
1. Deploy the V7.71 ZIP to the existing Netlify **test** site and verify against real GitHub access, including private Google Sheets notes/board read/write.
2. Execute the **secret-backed** GitHub NIL scorer end-to-end on a safe shadow run: decrypt, season context, the one-time v2→v3 baseline migration, and Stock Watch atomic output.
3. Confirm first game-day ESPN full/partial source coverage and an as-of replay. No fake scores or price movement before valid games.
4. Import/freeze the site's existing 2026–27 freshman valuation baselines into Stock Watch for **full rookie leaderboard coverage**; site rookie price fallbacks are already present.
5. Automate separate 2026–27 player shot, on/off and position feeds. The UI can load those paths but they currently are not populated by GitHub main.

Do not merge a draft PR simply because unit tests passed; the last two runtime checks are release blockers for automatic NIL publication. The public branch includes modeled market prices only, not private asking prices, notes, staff evaluations or secret model artifacts.
