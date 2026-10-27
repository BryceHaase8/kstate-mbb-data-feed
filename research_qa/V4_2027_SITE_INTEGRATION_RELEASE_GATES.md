# 2026–27 NIL V4 preseason site integration — staging status 2026-10-27

## What exists in this research branch

- `public/stock_watch/v4_preseason_2027_candidate.json`: **3,051 verified ESPN-ID identities** (matches the exact ID set of the existing main anchor).
- Original V4 model was reconstructed offline once using user-provided frozen 2025–26 Torvik player/stat and team results; **2,999** historical players have identity-verified V4 prices.
- **52** unverified historical identities retain their exact current public preseason prices. They are not guessed or replaced.
- Two V4 prices originally <$20K are set to the existing $20K publication floor. Original raw V4 prices are retained in the private offline audit, not here.
- `public/stock_watch/preseason_2027_legacy_2026_10_24.json`: exact archived previous 3,051-player anchor for rollback.
- The *existing* `preseason_2027.json`, monthly history, and published `nil_estimation_model_2027.json` are **unchanged** in this branch.
- `scripts/nil_model/nil_season_engine.py`: research-stage policy v3 that updates V4-based prices based on the **same auxiliary model's current/reference ratio**, not toward its absolute price level.
- One-time composition, identity coverage scripts, and dependency-light regression tests.

## Checks performed

- New-vs-old set of 3,051 IDs matches exactly (identity FNV-1a 0x855c55ab).
- Compared all candidate prices to the legacy file: 2,999 changed to V4, 52 are unchanged.
- Median absolute ratio difference: about 15%; 36 players change 2x or more, none change 4x.
- Belmont frozen V4 regression sentinels: Drew Scharnowski $2,381,092, Jabez Jenkins $296,117, Graydon Lemke $87,689, Cooper Haynes $77,350.
- The V4 rebuild is a **one-time initialization**; Torvik player-level data are NOT a dependency of this season's daily jobs.
- 2026–27 roster/ESPN box automatic publication still depends on the first real games and matching Torvik *team* context.

## Deliberate production blockers: DO NOT MERGE YET

1. The existing scheduled publishing safeguards (`validate_publish.py`, `publish_guard.py`, `record_stock_history.py`) currently enforce the *old* v2 price policy. The newly authored research engine announces v3; merging only this engine would fail and must not happen.
2. New baseline is not yet in the live filename `preseason_2027.json`. One explicit release must move it there and update the Stock Watch manifest, while preserving old anchor under its archive name. No historical daily Stock Watch dates existed as of the audit.
3. Existing website-owned **freshman and international preseason valuations must remain authoritative**. They are not in this 3,051-player 2025–26 source anchor and cannot be re-created or overwritten by this research branch. Verify the site overlay as part of release.
4. The staged 5,541-player 2026–27 roster was previously marked `import_ready=false` pending QA. Do not claim complete roster/in-season coverage until that current-year ESPN crosswalk passes.
5. Verify a full preseason dry run, an early-game partial feed dry run, and a multiple-game as-of replay in an isolated Actions job. QA on GitHub source and local synthetic fixtures is not a production end-to-end run.

## Release path once gates pass

A. Freeze/approve exact 2027 roster/website freshman precedence; B. separate archived anchor and update live preseason baseline **once** with a versioned migration; C. align all v3 release validators without relaxing the daily source, price drift, or identity guards; D. run test-only as-of game replay and check no-game/no-price movement; E. merge to main only when green; F. verify published price JSON and 2027 Stock Watch after a real game.

Branch intentionally contains neither decrypted fitted NIL model nor internal staff labels/asking prices or board information.
