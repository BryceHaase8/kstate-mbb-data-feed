# Verified V4 versus existing live-baseline audit — 2026-10-27

Read-only audit; no prices or private identities committed.

- Existing `main/public/stock_watch/preseason_2027.json`: **3,051** frozen model estimates.
- Exact V4 values from a private 22-player benchmarking workbook: **22** ESPN-ID-verified reference prices.
- Intersection: **10** of those V4 benchmark athlete IDs are in the 3,051-price frozen file.
- Exact dollar agreement for those 10: **zero**.
- **12** of the verified V4 benchmark ESPN IDs are absent from that frozen file.
- The staged 2026–27 roster research candidate contains **5,541** players and has `import_ready=false`.

The available national preseason anchor is demonstrably **not the V4 original pricing table**, even where identities overlap. Do not relabel it or claim the requested full-roster V4 switch is complete.

Research-only code has been added under `scripts/nil_model/v4_relative_update_research.py`; it updates a verified baseline using auxiliary model price *ratios* and a prior-frozen model version. `scripts/nil_model/v4_baseline_coverage_research.py` checks coverage before any future national release.

To activate nationally: source an original full V4 export with ESPN IDs, reconcile all current roster IDs, freeze new auxiliary preseason projections for the same frozen version of the scorer, backtest chronological checkpoints, and pass the preexisting immutable Stock Watch and published-pricing guards. No main, deployment, or scheduled updater modification is included.
