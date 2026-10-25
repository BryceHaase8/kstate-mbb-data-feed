# V7.64 — Same GitHub Repository: NIL Estimation Model + Stock Watch

Use the **existing public GitHub repository** `BryceHaase8/kstate-mbb-data-feed`.
No new repository, no new GitHub schedule, and no Netlify token are required.

1. Copy the overlay contents into the existing repository root, allowing the supplied
   `.github/workflows/daily-update.yml` to replace the prior file. Commit/push once.
   Commit only this overlay, NOT any decrypted model or the private setup key.
2. Add ONE GitHub Actions repository secret `NIL_MODEL_KEY` using the value in the
   separately provided private text file (`NIL_GitHub_One_Time_Secret_V7_64.txt`).
   Settings → Secrets and variables → Actions → New repository secret.
3. The next scheduled data update will validate ESPN statistics, decrypt the fitted
   model in the runner, calculate prices, validate national outputs, and append a
   daily Stock Watch snapshot only if real 2026–27 evidence is present. Everything
   is then committed in a single GitHub change.
4. Deploy the matching V7.64 website ZIP once; all later price/history refreshes
   come from GitHub. No need to redeploy Netlify for each daily update.

## Privacy
The fitted CatBoost model is **encrypted** in `scripts/nil_model/model.joblib.aesgcm`.
The decryption key exists only as the repository Actions secret. The public repo
contains the inference source, public historical team context, and public model-
generated NIL predictions. It contains no staff evaluations/asking prices.

## Safety
If `NIL_MODEL_KEY` is missing, only the existing factual data refresh runs; it does
not publish stale or simulated NIL changes. If the NIL model fails its checks, the NIL step reports a failure while validated
ESPN factual-data updates continue. The last good NIL snapshot stays intact. The same workflow retains its old season cron schedule.

The Torvik team-strength JSON is still fetched from the repository's existing
`torvik-daily-json-research-2026` branch; if that input is stale or unavailable after
2026–27 games start, the model publication fails closed. This is NOT a separate repo.

*Validation caveat:* This is ready for a controlled rollout, but an end-to-end run
against actual November 2026 games cannot be performed before those games exist.
