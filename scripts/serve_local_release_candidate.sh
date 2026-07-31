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

export CFF_GIT_SHA="$(git rev-parse HEAD)"
export CFF_GIT_BRANCH="$(git branch --show-current)"
export CFF_RELEASE_PROJECT_ID="$(git rev-parse --short=12 HEAD)"
# Never attach a release-candidate launch to the generic development compose
# project. A commit-scoped project keeps its API, worker, and database from
# being mistaken for a previously started local stack.
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-cff-rc-${CFF_RELEASE_PROJECT_ID}}"
export API_PORT="${API_PORT:-8000}"
export WEB_PORT="${WEB_PORT:-8080}"
# The candidate API reaches Postgres over Docker's private ``db`` network; it
# does not need the database exposed on the host.  Keep an opt-in diagnostic
# binding for direct audits, but choose a free port when none is supplied so a
# preserved generic/local database can never prevent the candidate from
# starting or make the browser talk to a stale stack.
if [[ -z "${DB_PORT:-}" ]]; then
  export DB_PORT="$(python3 -c 'import socket; sock = socket.socket(); sock.bind(("127.0.0.1", 0)); print(sock.getsockname()[1]); sock.close()')"
else
  export DB_PORT
fi
export CFF_RUNTIME_ID="${CFF_RUNTIME_ID:-$(uuidgen | tr '[:upper:]' '[:lower:]')}"

PYTHONPATH=. uv run python scripts/check_release_source_integrity.py
PYTHONPATH=. uv run python scripts/audit_preseason_source_contract.py --source-dir reports/source-imports/2026

docker compose up --build --detach db api web lifecycle_worker
docker compose ps

printf '\nRuntime identity:\n'
curl --fail --silent --show-error --max-time 10 "http://127.0.0.1:${API_PORT}/health/runtime"
printf '\nStatic UI: http://127.0.0.1:%s/\n' "$WEB_PORT"
printf 'Candidate database audit port: 127.0.0.1:%s\n' "$DB_PORT"
