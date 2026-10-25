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
