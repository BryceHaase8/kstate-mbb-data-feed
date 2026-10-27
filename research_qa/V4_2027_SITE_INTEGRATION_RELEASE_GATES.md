# 2026-27 opening week: consolidated V4, HS freshman, and roster coverage
**Matching frontend build:** Portal V7.73 TEST. **Do not deploy Netlify or merge GitHub PR before one final test-site pass.**

## Frozen starting values (ESPN IDs)
- Original V4: **3,052** (includes Kansas State Timo Malovec, ID 5281366, $791,196)
- Preserved site's HS freshman-model baseline: **1,420**
- Retained older NIL-model starting values not in V4 or HS: **733**
- Existing site's explicitly unmodeled **$50,000 provisional placeholders**: **805**
- **6,010 disjoint ESPN-ID frozen prices** in `public/stock_watch/preseason_2027.json`. No historical dated snapshots changed.
- The last 805 are a **coverage placeholder**, not verified market prices; the website labels them as such, and the automatic publisher does not promote them to V4.
- `public/stock_watch/roster_other_preseason_2027_candidate.json` records each non-V4, non-HS price provenance. Previous published v2 anchor preserved independently for rollback.
- The staged 2027 roster has 5,541 players; cross-referencing the retained historical model and these frozen anchors found **zero IDs without either a current published legacy estimate or a frozen anchor**.

## CI / Shadow proof on Oct 27, 2026
- Current GitHub PR unit test workflow PASS, including the exact 6,010-price, 4-source reconciliation.
- Secret-backed shadow refresh PASS: **12,682** price records, `policyVersion=3`, full model JSON 3,088,066 bytes (less than the site's 5,000,000-character proxy guard), no invented games or preseason Stock Watch change.
- Two synthetic game records in isolated runner PASS: one updated player, exact unchanged V4 preseason dollar anchor, one dated Stock Watch entry with all 1,420 freshmen and all 1,538 roster-only anchors preserved.
- Reference shadow run: https://github.com/BryceHaase8/kstate-mbb-data-feed/actions/runs/40550512784
- Synthetic data, private model key and decrypted model never committed or pushed. `main` and Netlify are untouched.

## Release order
1. Deploy the *complete matching Portal V7.73* ZIP **once to the TEST Netlify site**, retaining Netlify functions, and verify live GitHub/Google Sheets data.
2. On test, check V4 examples and Malovec; ranked and school-fallback freshmen; a preserved legacy-price player and a transparent unmodeled placeholder; Stock Watch's awaiting-games status; team, game, profile, board, agent, notes and roster features.
3. After the test passes, deploy the exact same ZIP to production **first**. Only then merge draft PR #5 so the v3 GitHub publisher and website baseline contract switch together.
4. Confirm price API response, no preseason history until real games, then first genuine official 2026-27 game update and exactly one dated snapshot. Stop deployment on failures.

Not yet promised for season day one: fully automated shot-location/on-off/position PBP publishers, new freshman market update calibration beyond frozen initial values, or non-provisional valuations for the 805 unmodeled cases.
