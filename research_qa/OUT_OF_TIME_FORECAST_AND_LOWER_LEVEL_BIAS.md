# V3 next-season predictive research / cross-level bias
Research only, 2026-10-18. Not a Portal or NIL valuation deployment.

## Properly out-of-time retrospective forecast
Matched 2022–2026 provider player tables by persistent pid, and teams by exact school name.
Source rotation >=15 games and >=10 MPG; target rotation >=10 games and >=10 MPG.
Training 2022->23, 2023->24, 2024->25, holdout 2025->26.
Alpha selected on 2024->25 without touching final 2026 target.
Predictions use last-season player BPM/box and last-season source/destination team strengths. They do NOT use future team result as a predictor.

Holdout (2025->26) on 1665 returners:
- Carry forward past player BPM: MAE 2.202; Spearman 0.742
- BPM plus box: MAE 1.922; Spearman 0.772
- BPM plus box and past team context: MAE **1.861**; Spearman **0.786**
- Overall MAE improvement 0.342, 15.5%, paired bootstrap 95% interval 0.280–0.404

159 non-high-major players transferring into major conferences:
- Carry-forward MAE 2.506; context-aware MAE 1.726
- Improvement 0.779 (31.1%); 95% bootstrap interval 0.546–1.025
- Spearman 0.442 -> 0.518
These are conditional-on-playing statistics, not probabilities of roster retention or rotation.

## Why low-level players are over-ranked in 2026 descriptive V3
The box-only model lacks relative competition and team strength inputs. On 2193 eligible players, V3 estimate minus true Torvik BPM in 2025-26 averaged:
- Final Top 80 teams: **-1.232**
- Final team ranks 81-175: **+0.332**
- Final team ranks 176+: **+1.880**
Across players, residual vs 2026 team adjusted efficiency has Pearson correlation **-0.716** (descriptive association; retrospective team ratings known only after season).
On identical eligible samples, 93 true Torvik Top 100 BPM players attended Top 80 teams, but only 69 of the box-proxy Top 100 did. The box proxy includes nine players from final team ranks 176+, while Torvik's top100 includes none.

Examples (V3 impact / 2026 true Torvik BPM):
- Allen Graves (Santa Clara): 14.58 / 14.22 — outstanding within level; *transfer translation* uncertain.
- Jackson Holcombe (Utah Valley): 10.53 / 6.54
- Kyle Evans (UC Irvine): 10.41 / 7.77
- Jerald Colonel (Stephen F. Austin): 9.97 / 8.08
- Aidan Kehoe (Navy): 9.46 / 7.22
- Owen Aquino (High Point): 9.31 / 5.79

High block/rebound box production can skew top ranks; this does not establish universal bias against guards or for every center. Preserve distinct metrics for current-level impact and projected Big 12 impact.

## RAPM cannot be declared predictive yet
2025-source luck-only RAPM was rebuilt on a separated research branch using official minutes. First QA run: 592 games, only 54,096 clean possessions and ~8.16% player-minute coverage (versus ~419k clean possessions in prior 2026 fit). The independent next-season RAPM uplift test was deliberately prevented from publishing an answer because historical lineups fail too often. Refer to `research_qa/impact_v3_2025_to_2026_rapm_incremental.json` and the 2025 audit.

V3's same-season overlap with Torvik Top 100 is **not** a predictive-validity test. Even the historical BPM forecast does not establish RAPM uplift; that requires additional independent year-specific lineup data and adequate quality gates.

No Netlify deployment, production branch updates, or raw provider CSV uploads.
