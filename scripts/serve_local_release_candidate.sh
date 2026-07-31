#!/usr/bin/env bash
set -euo pipefail

# Launch the same static web/API/worker topology used for release verification.
# A dirty worktree may be used only when the caller explicitly marks it as
# diagnostic; it must never be described as a release candidate.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! git rev-parse --verify HEAD >/dev/null 2>&1; then
  echo "Cannot start a release candidate without a Git commit." >&2
  exit 1
fi

if [[ -n "$(git status --porcelain --untracked-files=normal)" && "${ALLOW_DIRTY_RELEASE_CANDIDATE:-false}" != "true" ]]; then
  echo "Refusing to label a dirty worktree as a release candidate." >&2
  echo "Commit or isolate the changes first. Set ALLOW_DIRTY_RELEASE_CANDIDATE=true for diagnostic use only." >&2
  exit 2
fi

export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-cff-playground}"
export API_PORT="${API_PORT:-8000}"
export WEB_PORT="${WEB_PORT:-8080}"
export DB_PORT="${DB_PORT:-5433}"
export CFF_GIT_SHA="$(git rev-parse HEAD)"
export CFF_GIT_BRANCH="$(git branch --show-current)"
export CFF_RUNTIME_ID="${CFF_RUNTIME_ID:-$(uuidgen | tr '[:upper:]' '[:lower:]')}"

docker compose up --build --detach db api web lifecycle_worker
docker compose ps

printf '\nRuntime identity:\n'
curl --fail --silent --show-error --max-time 10 "http://127.0.0.1:${API_PORT}/health/runtime"
printf '\nStatic UI: http://127.0.0.1:%s/\n' "$WEB_PORT"
