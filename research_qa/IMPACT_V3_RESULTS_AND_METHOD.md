# Impact V3 — 2025–26 Research Audit (October 17, 2026)

**Status: research only.** No live Portal updates, no deployment, and no changes to `main`.
All rankings below are retrospective; the model is not validated to forecast next-season transfer outcomes.

## Why V2 failed

The old Torvik+luck RAPM subtracted an external team-efficiency expectation **in addition to** fitting team indicators and five offensive/defensive players. Team and player columns overlap substantially; the resulting player coefficients can absorb or be stripped of large team offsets. The published unfiltered V2 top 100 consisted largely of implausible names, while many established stars fell hundreds of places.

## V3 methodology

1. Historical player box stats (2021–22 to 2024–25) train a **box-only estimated BPM proxy** using regularized degree-two regression. Calibration target is Torvik player BPM, not next-season outcomes. Inputs are GP, MPG, production per 30, attempts, shooting efficiency, playmaking, turnovers and steals/blocks. This step uses historical training files held locally, not Torvik team-strength offsets.
2. Use the **luck-only** RAPM coefficients from `rapm_v2_player_comparison_2026.csv`. Those coefficients already control for actual teammates and opponents through lineups/team indicators; we do not subtract Torvik team-strength values from the RAPM outcome again.
3. Learn an intercept/slope mapping from estimated BPM to expected luck-only RAPM on high-exposure players. Add **only the RAPM residual** to BPM, capped and shrunk by verified possessions and individual coverage; do not average incompatible raw coefficients.
4. Missing RAPM contributes zero correction; players are never promoted solely because of a small RAPM sample.
5. Rank national players with at least **20 GP / 18 MPG**, keeping the all-player export separate.

### V3 national run

- **5,019** 2025–26 ESPN players, **2,215** eligible for national rank.
- **4,838** ESPN athletes have a V2 luck-RAPM row; **2,051** substantial exposures for model centering.
- Median |RAPM correction|: **0.060** impact points; 95th percentile: **0.355**; maximum: **0.918**.
- 2026 held-out box-BPM replication after 2022–25 training: **MAE 1.66 BPM**, **R² 0.720**, **rank Spearman 0.861**, calculated against historical Torvik BPM among at least 20 GP and 18 MPG.
- Holding the eligibility filter constant (20 GP/18 MPG), **5** of the historical Torvik Top 100 appeared in the old V2 Torvik+luck top 100; **58** appeared with the V3 estimated-BPM baseline alone, **60** with V3 BPM + luck-RAPM. Matching is by normalized names; uncommon name variations can affect overlap.
- The previously exported **unfiltered** V2 top 100 overlapped just **4** of the historical Torvik Top 100. Do not compare that count as identical methodology to the eligibility-matched checks above.

**Interpretation:** V3 substantially repairs the implausible rankings. Most of the improvement is from restoring a calibrated box-score foundation; the RAPM add-on improves this particular BPM-overlap benchmark by only two players. This is not yet evidence of better future-player prediction.

## Important limitations before production

- The 2026 luck RAPM is retrospective; its shooter baselines exclude the same game but use other full-season games including games in the future. Live predictions require chronological, past-only shooting priors.
- 2025–26 V2 RAPM covers roughly **57%** of official player-minutes after data-quality gates. Player-specific coverage estimated from ESPN minutes is an approximation.
- Team effects and player effects remain partly non-identifiable. Excluding Torvik offsets prevents the strongest observed distortion but does not guarantee valid cross-conference opponent adjustment.
- The historical BPM calibration and 2026 test validate reproduction of a known metric, **not** prediction of the eight Big 12 role outcomes. The next test needs frozen early-season predictions and following-season labels.
- Our baseline relies on box-score efficiency and can favor productive interior players; review guards/wings and translation across competition levels separately.
- The `research_qa/ebpm_v3_coefficients.json` file permits inference without Torvik for daily player box statistics, but **daily V3 RAPM publication is NOT activated**; the 2027 RAPM rebuild is still incomplete.

## Research artifacts

- `scripts/impact_v3_research.py`: V3 scoring and sample weighting.
- `scripts/train_ebpm_v3.py`: fully reproducible local training from provider CSVs (provider records should not be republished into a public repository).
- `research_qa/ebpm_v3_coefficients.json`: frozen trained parameters.
- `research_qa/impact_v3_top_100_2026.csv`: national ranking sample.
- `research_qa/impact_v3_all_2026.csv`: all 5,019 player impact estimates.
- `research_qa/impact_v3_audit_2026.json`: data checks, summary, and BPM vs RAPM ablations.
- `.github/workflows/impact-v3-research.yml`: reproducible isolated research runner.

## Recommended next model work

First validate the V3 BPM feature mapping against independent box data and investigate high-major/guard/big position bias. Then evaluate 2022–26 historical seasons with **chronological** PBP RAPM, compare predicted next-season BPM/role labels for BPM alone vs BPM plus RAPM, and calibrate RAPM weighting using future-season validation rather than same-year BPM agreement. Keep all outputs on a research branch until those checks pass.
