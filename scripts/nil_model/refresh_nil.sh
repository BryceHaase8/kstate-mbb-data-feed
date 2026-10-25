#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
cd "$ROOT"
: "${NIL_MODEL_KEY:?NIL_MODEL_KEY must be configured as a repository Actions secret}"
python "$HERE/test_safety.py"
python "$HERE/decrypt_model.py"
trap 'rm -f "$HERE/nil_estimation_model_core_shadow.joblib"' EXIT
mkdir -p "$RUNNER_TEMP/nil_candidate"
# Team strength comes from the existing Torvik scraper BRANCH IN THIS SAME REPO.
curl --fail --retry 4 --retry-delay 3 -L --max-time 90  -o "$RUNNER_TEMP/nil_candidate/team_2027.json"  'https://raw.githubusercontent.com/BryceHaase8/kstate-mbb-data-feed/torvik-daily-json-research-2026/research_qa/torvik_team_strength_2027_validated.json'
python "$HERE/nil_season_engine.py"  --factual public/portal_factual_data.json  --archived-teams "$HERE/source_data/torvik_team_context.json"  --current-teams "$RUNNER_TEMP/nil_candidate/team_2027.json"  --as-of "$(date -u +%F)"  --output "$RUNNER_TEMP/nil_candidate/nil_estimation_model_2027.json"  --min-coverage .50
python "$HERE/validate_publish.py"  --new "$RUNNER_TEMP/nil_candidate/nil_estimation_model_2027.json"  --manifest "$RUNNER_TEMP/nil_candidate/nil_estimation_model_2027.json.manifest.json"  --previous public/nil_estimation_model_2027.json
python "$HERE/publish_guard.py"  --new "$RUNNER_TEMP/nil_candidate/nil_estimation_model_2027.json"  --old public/nil_estimation_model_2027.json  --source public/portal_factual_data.json
# Compute snapshot in temp first, so any history-recording failure does not
# modify the checked-out published Stock Watch data.
cp -a public/stock_watch "$RUNNER_TEMP/nil_candidate/stock_watch"
python "$HERE/record_stock_history.py"  --new "$RUNNER_TEMP/nil_candidate/nil_estimation_model_2027.json"  --root "$RUNNER_TEMP/nil_candidate/stock_watch"
cp "$RUNNER_TEMP/nil_candidate/nil_estimation_model_2027.json" public/nil_estimation_model_2027.json
cp "$RUNNER_TEMP/nil_candidate/nil_estimation_model_2027.json.manifest.json" public/nil_estimation_model_2027.json.manifest.json
cp -a "$RUNNER_TEMP/nil_candidate/stock_watch/." public/stock_watch/
echo 'NIL model + Stock Watch passed: committed together with the validated basketball feed.'
