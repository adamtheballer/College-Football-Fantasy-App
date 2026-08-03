#!/usr/bin/env bash
set -euo pipefail

# Read-only beta runtime gate.  It never stops containers or deletes volumes.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

readonly EXPECTED_BRANCH="codex/runtime-provenance-contract"
readonly EXPECTED_PORT="18080"
readonly EXPECTED_PROJECT="cff_beta"
readonly ENV_FILE="${CFF_BETA_ENV_FILE:-/private/tmp/cff-local-beta.env}"
readonly DISALLOWED_PUBLIC_PORTS=(3000 4173 5173 8000 8001 8080 18000 18081)

fail() { echo "BETA PREFLIGHT FAILED: $*" >&2; exit 1; }
[[ -r "$ENV_FILE" ]] || fail "private beta environment file is unavailable: $ENV_FILE"
# shellcheck disable=SC1090
source "$ENV_FILE"
[[ "${CFF_BETA_DATA_VOLUME:-}" ]] || fail "CFF_BETA_DATA_VOLUME is required in the private beta environment"
[[ "${BETA_ACCESS_ENABLED:-}" == "true" ]] || fail "BETA_ACCESS_ENABLED must be true"
[[ "${PLAYER_HEADSHOTS_ENABLED:-}" == "false" ]] || fail "PLAYER_HEADSHOTS_ENABLED must be false"
[[ "${BETA_ACCESS_CODE_HMAC_SECRET:-}" != "change-me-beta-access-code-hmac" ]] || fail "beta code secret is not configured"
[[ "${BETA_ACCESS_RESERVATION_SECRET:-}" != "change-me-beta-access-reservation" ]] || fail "beta reservation secret is not configured"
[[ -z "${VITE_API_BASE_URL:-}" || "${VITE_API_BASE_URL}" == "/api" ]] || fail "VITE_API_BASE_URL must be /api for the one-port beta runtime"
grep -Fq 'ENV VITE_API_BASE_URL=/api' Dockerfile.web || fail "web image is not pinned to the same-origin /api base URL"

branch="$(git -c core.fsmonitor=false branch --show-current)"
[[ "$branch" == "$EXPECTED_BRANCH" ]] || fail "expected branch $EXPECTED_BRANCH, found ${branch:-detached HEAD}"
python3 scripts/check_release_source_integrity.py || fail "release-critical source is dirty or incomplete"
git -c core.fsmonitor=false fsck --full --no-dangling >/dev/null || fail "Git object database failed fsck"

docker volume inspect "$CFF_BETA_DATA_VOLUME" >/dev/null 2>&1 || fail "required existing database volume is missing: $CFF_BETA_DATA_VOLUME"

running_projects="$(docker compose ls --format json 2>/dev/null | python3 -c 'import json,sys; print("\\n".join(x.get("Name", "") for x in json.load(sys.stdin)))' || true)"
while IFS= read -r project; do
  [[ -z "$project" || "$project" == "$EXPECTED_PROJECT" ]] && continue
  [[ "$project" == cff_* ]] && fail "another CFF Compose project is running: $project (stop it explicitly before beta launch)"
done <<< "$running_projects"

for port in "${DISALLOWED_PUBLIC_PORTS[@]}"; do
  listener="$(lsof -nP -iTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  [[ -z "$listener" ]] && continue
  echo "Detected unexpected public listener on port $port:" >&2
  echo "$listener" >&2
  fail "only http://127.0.0.1:$EXPECTED_PORT may be used for the local beta runtime"
done

listener="$(lsof -nP -iTCP:"$EXPECTED_PORT" -sTCP:LISTEN 2>/dev/null || true)"
if [[ -n "$listener" ]] && ! docker compose -p "$EXPECTED_PROJECT" ps --status running --services 2>/dev/null | grep -qx web; then
  fail "port $EXPECTED_PORT is already occupied by a non-beta process"
fi

echo "BETA PREFLIGHT PASSED: branch=$branch port=$EXPECTED_PORT volume=$CFF_BETA_DATA_VOLUME"
