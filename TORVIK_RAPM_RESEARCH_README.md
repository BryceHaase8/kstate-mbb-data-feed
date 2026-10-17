# Torvik JSON RAPM integration — isolated research branch

The published `YYYY_team_results.json` format has 45 ordered fields per team. The user-provided 2027 JSON and 2026 historical CSV have matching column positions: index 4 adjusted offense, 6 adjusted defense, 8 BarTHAG, 44 adjusted tempo. The 2027 preseason rows are 0-0 projections.

The single-request direct JSON GitHub Action test returned **HTTP 403 Forbidden**. No daily download is live, and no automated bypass is acceptable. Confirm permitted automated access with Bart Torvik before enabling daily refresh.

The reusable helper `scripts/rapm_torvik_team_context.py` calculates an expected opponent-efficiency baseline using season-matched adjusted offense and defense. It must be applied as a **response offset inside a new RAPM regression**, not as a post-hoc multiplier on a player's already-adjusted RAPM.

The verified historical Torvik↔ESPN crosswalk in the separate staff research package matches 365/365 2026 teams, and reusing it maps 364/365 of the uploaded 2027 preseason JSON (West Florida requires new ESPN ID verification). The full crosswalk is in the separate packaged research prototype; it has **not** yet been committed to this branch. Full historical Torvik-informed RAPM coefficients have **not** yet been fit.

No changes to GitHub main, production RAPM, Netlify or Portal. The feature remains gated until publisher access, crosswalk ingestion, independent coverage audit, historical model comparison and explicit approval.
