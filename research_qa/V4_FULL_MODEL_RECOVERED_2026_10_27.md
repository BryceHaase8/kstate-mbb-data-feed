# Original V4 model recovered — 2026-10-27

The user supplied the actual fitted `portal_nil_model_v4_package(4).zip` including V3 base and V4 residual scorer. We reconstructed **4,978** 2025-26 college-player V4 prices offline using the user's frozen 2025-26 Torvik player stats and 2026 team results, strictly for one-time preseason initialization.

Of the existing **3,051-player ESPN-ID research population**, **2,999** linked confidently to the historical Torvik snapshot: 2,966 exact player names + 2026 source-team rankings; 32 normalized-suffix name variants + exact rankings; one exact name/school and rank difference of 3. **52 remained unresolved** (51 without a name match, one team mismatch); preserve their existing website values.

Ten Belmont ESPN-ID benchmark V4 prices reproduced exactly, including Scharnowski $2,381,092, Jenkins $296,117, Lemke $87,689, and Haynes $77,350. No new Torvik player-stat dependency is needed for any *in-season* updates; these are offline frozen prior values. Two low-end V4 values are $19,685 and $19,820, requiring explicit $20,000 site-floor compatibility handling.

**Private recovery artifacts are available in the user's conversation, not committed to this public repository.** They include the complete ESPN-ID-to-V4 price mapping, an unresolved-ID audit, an offline raw V4 score list, the model provenance and reconstruction scripts. **Never commit the V4 .pkl/.cbm models or private market training labels to public branches.**

## Baseline compose rule

1. Load existing 2027 site frozen valuation by ESPN ID.
2. Replace only independently verified returning-player IDs with one-time reconstructed V4 prices.
3. Keep the existing valuation on all 52 unresolved research IDs, recording `EXISTING_SITE_FALLBACK` rather than falsely calling it V4.
4. Keep all previously assigned 2026-27 freshman prices unchanged, with the existing freshmen valuation feed taking precedence.
5. Build the new proposed baseline as a **separate versioned research artifact**. Do not overwrite the immutable 2026-10-24 Stock Watch anchor.
6. Reconcile against the full 2027 roster, including no-game freshmen; pass national ID completeness and publish history gates.
7. Freeze one auxiliary preseason projection per athlete, then calculate in-season relative movement versus the same auxiliary model version; only then consider publication.

Live `main`, the Netlify website, and Stock Watch remain unchanged. This research branch does not deploy.
