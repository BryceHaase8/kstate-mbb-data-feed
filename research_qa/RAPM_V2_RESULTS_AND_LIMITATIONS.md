# Official-minute-gated 2025-26 RAPM V2 — research results

**Status:** Fit completed and audited on isolated research branch. NOT validated for predictive use; NOT published to Portal or main.

## Core sample

- **3,972** games accepted; **419,361** clean possessions; **4,838** players in common across all variants.
- **57.0%** of eligible official player-minutes represented in the regression's accepted games.
- ESPN shot attribution: **146,132** three-point attempts and **108,359** free-throw attempts had luck correction applied on accepted possessions.
- **535** games with missing team Torvik context excluded (e.g. non-Division-I opponents); compare only identical 419,361 possessions across four models.
- Final 2025–26 Bart Torvik ratings, **365** matched team IDs. Historical full-season Torvik ratings are hindsight information and should not be treated as available to an earlier-season forecast.

## Four matched models

1. `baselineV1`: official-minute-gated RAPM refit on comparable 419k clean possessions (team indicators plus 5 offensive and 5 defensive player effects).
2. `torvikInformed`: same ridge design with an external Torvik offensive/defensive team-efficiency baseline subtracted from the observed scoring target.
3. `luckAdjusted`: same ridge design with possession points modified to reduce the effects of made/missed 3PT and FT attempts using regularized shooter estimates (current game excluded).
4. `torvikAndLuckAdjusted`: both outcome transformations.

The luck adjustment replaces shot-make variance in *included possessions*, retaining attempts and offensive rebounds, not adjusting 2PT attempts. The posterior shooter-rate estimator uses the remainder of the **same season**, including future games. It is retrospective and needs chronological as-of-date logic before live daily forecasting.

## Diagnostic findings

On the **2,051** players with at least 1,000 verified clean-possession exposures, correlation to the same-sample baseline:

- Torvik-only: **0.8731**
- Luck-only: **0.8115**
- Torvik plus luck: **0.5226**

Absolute change from same-sample baseline under combined Torvik+luck: median **1.41**, 90th percentile **3.68**, 95th percentile **4.525**, maximum **8.88** points per 100 possessions. Changes this large require careful examination before assigning these metrics to player-impact valuations or Big 12 success projections.

Selected ratings, each points per 100 possessions (**all 2025-26 retrospective research**):

| Player | Baseline, same 419k sample | Torvik only | Luck only | Both |
|---|---:|---:|---:|---:|
| Flory Bidunga | +8.79 | +6.56 | +4.82 | +2.60 |
| Milan Momcilovic | +6.89 | +3.29 | +3.94 | +0.34 |
| JT Toppin | +4.48 | +2.48 | +3.69 | +1.69 |
| Moustapha Thiam | +3.34 | +1.86 | +3.36 | +1.88 |
| Robert Wright III | +1.40 | -0.76 | +1.75 | -0.41 |
| Terrence Brown | -0.72 | -0.25 | -1.35 | -0.88 |

### Interpretation and limits

- V1 already adjusts for opposing and teammate lineups and includes team terms. Conditioning again on Torvik team strengths can make a model explain away genuine player contribution (double counting).
- Player coefficients represent residual scoring effects *conditional on the fitted design*. Torvik-conditioned coefficients are not automatically directly comparable to unconditioned estimates as standalone player quality scores.
- Changes in high-exposure players are too large to accept without future-season or rolling as-of-date validation.
- The refitted baseline differs from the prior 2026 official RAPM because 535 games were excluded for the same-sample Torvik comparison; among 4,838 shared players the median absolute change is 0.42 points per 100 possessions.
- The shooter luck adjustment is not a complete shot-quality model; it lacks defender distance, shot location and shot-creator features. Its shooter rates are stabilized posterior estimates, not true shot quality.
- **Do not promote any V2 coefficient to Portal, NIL, or player success predictions yet.**

## Links within research branch

- `research_qa/rapm_v2_model_2026.json`: all four fits and exposure data.
- `research_qa/rapm_v2_model_2026_audit.json`: full game/possession QA.
- `research_qa/rapm_v2_diagnostic_summary.json`: small staff review summary.
- `research_qa/rapm_v2_player_comparison_2026.csv`: per-player comparison of all four variants with ESPN player names and school.
- `scripts/rapm_v2_official_comparison.py`, `scripts/rapm_possessions_v2.py`: reproducible model and possession-luck parser.

## Recommended next research experiment

Before choosing a model, measure prediction or repeatability under truly chronological splits. Use only Torvik ratings available **as of the model date**, fit shooter priors on **past data only**, and evaluate changes to held-out *future* outcomes. Also test whether applying the Torvik offset in a model that already fits team indicators is reducing attribution to good players. Treat luck-only as the first separate candidate, and Torvik-informed coefficients as diagnostics until there is a demonstrable out-of-sample lift.

The Google Apps Script daily 2026–27 Torvik feed is independent research infrastructure; this historical 2026 fit does NOT yet update daily.
