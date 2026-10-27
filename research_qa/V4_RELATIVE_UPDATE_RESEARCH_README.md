# Research: V4-anchored NIL in-season price changes

**NOT LIVE. No workflow, Stock Watch, public pricing, or Netlify changes.**

This independent research branch tests the user's approach:

1. The **exact verified original V4 price** is the immutable preseason dollar anchor by ESPN athlete ID.
2. Freeze the new auxiliary model's **own preseason prediction** for that same ESPN ID.
3. As verified 2026–27 games arrive, run that same fixed auxiliary model on current evidence.
4. Update in log-relative space: `V4 * exp(w * log(aux_current / aux_preseason))`.
5. Without games or minutes, return **exact V4**. A model's disagreement with V4 at baseline cannot reprice anyone. Using different model versions without an explicit frozen rebasing audit is rejected.

`w` is the existing website's provisional nonlinear games/minutes evidence policy (about 90% at 30 games x 30 MPG); it is **not** historically optimized to NIL market outcomes. Recalculate only with validated as-of sources. Raw shooting percentages, very low minutes, injuries and DNP interpretation need further QA. Inputs must derive from ESPN factual feeds, own Impact, and Torvik **team** context, not Torvik player stats.

### Verified coverage blocker

Current `main/public/stock_watch/preseason_2027.json` has 3,051 frozen prices but labels its origin `NIL Estimation Model`; that is **not proof those are original V4 values**. Only 22 exact original V4 numbers have been independently verified in the private benchmark file. **Never** relabel the existing 3,051 as V4. This branch includes no private player labels.

2026–27 staged roster has 5,541 IDs, remains `import_ready=false` in its separate research QA. An approved full V4 export and current-roster ESPN-ID QA are needed to enable a national frozen baseline. An unpriced player is not silently assigned a fake V4 value.

### Release gates

- Obtain the complete ESPN-ID-keyed V4 frozen price file, or explicitly choose to use the present site prices **under their true provenance**, as a separate policy choice.
- Generate and version-freeze an auxiliary-model preseason prediction for each baseline athlete; V19 archived research scorer is **not yet feature-compatible** with the GitHub 2027 site feed.
- Verify the nightly GitHub job ingests actual current games before invoking the updater, and verify date, quality, sample size, Impact availability and team ratings.
- Chronologically backtest historical trajectories; inspect day-to-day jumps, cheap reserves, starters, up-transfers, and false injuries/DNP effects.
- Reuse immutable existing Stock Watch preseason history. Run test-site shadow scoring and publish guards before any explicit main deployment.

Run synthetic no-secret tests: `python -m unittest discover -s tests -p 'test_v4_relative_update_research.py' -v`.

Research file: `scripts/nil_model/v4_relative_update_research.py`; it produces a candidate JSON and an audit, never writes production files.
