#!/usr/bin/env bash
set -euo pipefail

# The only supported local public-beta entrypoint.  It never creates or
# chooses a database volume and never exposes a host API port.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
readonly ENV_FILE="${CFF_BETA_ENV_FILE:-$ROOT_DIR/.beta-runtime.env}"
readonly PROJECT="cff_beta"

[[ -r "$ENV_FILE" ]] || { echo "Missing private beta environment: $ENV_FILE" >&2; exit 1; }
# shellcheck disable=SC1090
source "$ENV_FILE"
export VITE_BETA_ACCESS_ENABLED="${VITE_BETA_ACCESS_ENABLED:-$BETA_ACCESS_ENABLED}"
export CFF_GIT_SHA="$(git -c core.fsmonitor=false rev-parse HEAD)"
export CFF_GIT_BRANCH="$(git -c core.fsmonitor=false branch --show-current)"
export CFF_WEB_GIT_SHA="$CFF_GIT_SHA"
export CFF_WORKER_GIT_SHA="$CFF_GIT_SHA"
export CFF_RUNTIME_ID="beta-${CFF_GIT_SHA:0:12}"
eval "$(python3 scripts/beta_runtime_dataset_versions.py --shell)"

scripts/preflight-beta-local.sh
docker compose --env-file "$ENV_FILE" -p "$PROJECT" -f docker-compose.yml -f docker-compose.beta-local.yml up --build --detach db api web lifecycle_worker

for _attempt in $(seq 1 60); do
  runtime="$(curl --fail --silent --max-time 3 http://127.0.0.1:18080/api/health/runtime 2>/dev/null || true)"
  if [[ -n "$runtime" ]] && python3 -c 'import json,sys; d=json.loads(sys.stdin.read()); assert d["git_sha"] == sys.argv[1]; assert d["runtime_mode"] == "release_candidate"; assert d["scoring_mode"] == "disabled"; assert d["sportsdata_enabled"] is False; assert d["provider_polling_expected"] is False; assert d["email_enabled"] is False' "$CFF_GIT_SHA" <<< "$runtime"; then
    echo "BETA READY: http://127.0.0.1:18080/"
    exit 0
  fi
  sleep 2
done
echo "Beta API did not become ready on the required same-origin route." >&2
exit 1
