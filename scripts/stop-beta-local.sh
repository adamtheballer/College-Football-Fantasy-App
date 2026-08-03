#!/usr/bin/env bash
set -euo pipefail

# Stop only the fixed beta Compose project.  Named database volumes are never
# removed, including on failure.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
readonly ENV_FILE="${CFF_BETA_ENV_FILE:-$ROOT_DIR/.beta-runtime.env}"
[[ -r "$ENV_FILE" ]] || { echo "Missing private beta environment: $ENV_FILE" >&2; exit 1; }
# shellcheck disable=SC1090
source "$ENV_FILE"
# Compose validates these release-data identifiers even for `down`, before it
# discovers existing project containers. Derive them from the committed source
# manifest exactly as the start command does so a controlled stop cannot be
# blocked by an otherwise complete private environment file.
export CFF_GIT_SHA="$(git -c core.fsmonitor=false rev-parse HEAD)"
export CFF_GIT_BRANCH="$(git -c core.fsmonitor=false branch --show-current)"
export CFF_WEB_GIT_SHA="$CFF_GIT_SHA"
export CFF_WORKER_GIT_SHA="$CFF_GIT_SHA"
export CFF_RUNTIME_ID="beta-${CFF_GIT_SHA:0:12}"
eval "$(python3 scripts/beta_runtime_dataset_versions.py --shell)"
docker compose --env-file "$ENV_FILE" -p cff_beta -f docker-compose.yml -f docker-compose.beta-local.yml down --remove-orphans
echo "Beta containers stopped; database volume was preserved."
