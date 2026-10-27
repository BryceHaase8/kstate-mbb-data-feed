# Top-100 international players without previous college production — 2026–27 preseason review

**As of 2026-10-27.** Source candidate pool: [full exact ESPN-ID review board](international_top100_no_college_review_2027.json).

## Eligibility and filtering

- 138 candidates on verified top-100 Torvik teams have no 2022–23 through 2025–26 ESPN D-I player-box record and a *possible* international birthplace clue. This is a screening list, not a verified exhaustive roster of all internationals.
- Review professional and developmental-club histories individually using the school bio and, if available, the league's statistics.
- Exclude players who have other college stats, including JUCO / NAIA / non-D-I, from this specific calibration. Initial excluded profiles: Wesly Rosa and Alex K'Medehouto.
- 12 separately expert-calibrated prices are immutable during this step.
- First 22 independently documented players received research-based opening-market NIL estimates. Sources, evidence, competition tiers and exact ESPN IDs are recorded separately in `public/stock_watch/international_top100_noncollege_2027_priors.json`. Models are not asserting true payments.
- 102 unresolved first-pass candidates were not repriced. Next work is evidence-based verification; no automatic salary premium by surname, birthplace or league branding.

## Calibration logic

The 12 independently reviewed international prior prices span $700K to $3.5M and serve as value-scale anchors. Research prices for this first-pass set use each player's **actual prior basketball competition**, performance and role, FIBA/NBA pedigree, age and expected college transferability; they are intentionally distinct from the user's staff-reviewed valuations and are only moderately confident. Senior top-league starters/high prospects are distinct from limited-minute top-league players, second-division starters, and development/youth-only players. No NBA draft proxy is applied solely for attending a famous European club's U22 team.

Observed previous team NIL amounts are not a model constraint; roster value changes are an output. Verified contract buyouts must not be counted as player NIL.

## Opening-price versioning and safety

- `preseason_2027_pre_international_20261027.json`: source 6,057-player pricing before 12 expert changes
- `preseason_2027_before_top100_20261027.json`: 6,057-player snapshot **after** those 12 expert values and **before** 22 research changes
- `preseason_2027.json`: current 6,057-player base after 12 + 22 separate versioned opening-prior calibrations
- Tests and a complete encrypted shadow scoring run require exact ESPN-ID matches, all unselected prices unchanged, and no fake Stock Watch movement.

**Outstanding technical issue, unrelated to baseline publishing:** `nil_season_engine.py` freezes no-prior players' price after current season evidence, because it lacks an approved neutral reference. It must be corrected with a separate evidence-gated relative model before live games begin. Do not infer a pro player's college scoring solely from their previous league, and never blend toward the absolute raw auxiliary model scale.
