# V7.64 GitHub-integrated NIL Estimation + Stock Watch

Existing ESPN scheduled Actions workflow now also computes the model **within the same run**,
using validated local data, current team-strength data from the existing repo branch,
and the frozen 2025–26 baseline. It writes `public/nil_estimation_model_2027.json`,
`public/stock_watch/manifest_2027.json`, and date-scoped monthly history once new
season production exists. One Actions secret decrypts the fitted model within the runner.

Website points to the same existing public GitHub raw feed; Netlify Stock Watch reader
now requires no token, private repo, or external service. No private staff data published.

This is a release artifact; it does NOT itself configure the repo secret or deploy a website.
