# NIL Estimation Model / Stock Watch — operating notes

This is part of the **existing** `kstate-mbb-data-feed` GitHub Actions update, not a second scheduler.

1. The existing ESPN factual build and validation run first.
2. GitHub Actions checks the `NIL_MODEL_KEY` repository secret.
3. In an isolated job step, the fitted model is decrypted temporarily; the Bayesian season scorer reads ESPN facts and validated same-repository Torvik team context.
4. Pricing guards run before `public/nil_estimation_model_2027.json` and `public/stock_watch/` are updated. On model failure, preserve last verified model data and **do not interrupt factual-data publication**.
5. The website reads the published files directly; new valuation snapshots do not require new Netlify deployments.

**Verification:** Look for *Calculate validated NIL and record Stock Watch* in the `Update basketball factual feed + NIL Stock Watch` workflow. A successful overall run is insufficient if NIL scoring was skipped or had a tolerated failure. During preseason, history should have no in-season movement until real 2026–27 box-score evidence arrives.

The repository is public: **never commit** the `NIL_MODEL_KEY` secret, a decrypted `.joblib`, staff evaluations, asking prices, or board information. Public outputs contain model-generated open-market estimates only.

The official preseason benchmark is fixed at the frozen `public/stock_watch/preseason_2027.json` anchor. Do not silently retrain or recompute its prices.


## 2026-10-27 final ESPN roster coverage

The October 27 ESPN roster recheck contains 5,541 exact athlete IDs. Of these, 5,494 IDs occur in the original 6,010-player launch anchor. The other 47 are appended in `public/stock_watch/roster_2027_new_id_v4_proxy_addendum.json` without changing **any** original launch price. The exact 6,010-record original is archived as `public/stock_watch/preseason_2027_original_6010_2026_10_27.json`, and the expanded `preseason_2027.json` has 6,057 frozen starting prices.

Nine of the 47 had a previous ESPN-production-based model price. The remaining 38 have no usable historical ESPN production. Their estimates are **V4-team-cohort proxies**, not an application of the fitted V4 model to nonexistent statistics and not proven NIL payments. Prices are generated from the existing original V4 prices of players at the same team, 2027 Torvik **team** rank, and broad ESPN position. The complete fixed formula and per-player inputs are recorded in the addendum. No Torvik player data, name-based joining, invented stats, or national-origin guessing are used.

Preseason launch values should not be silently recalculated as new rosters/headshots arrive. Future ESPN-ID additions need an additive baseline QA review; adjust the input and published baseline together, keeping the original snapshot for rollback. International recruits with no U.S. college production are **particularly uncertain** and should receive a dedicated evidence-driven calibration later. This stopgap must not be presented to staff as an accurate international market study.
