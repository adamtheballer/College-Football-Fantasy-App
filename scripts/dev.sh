#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$REPO_ROOT"

python3 scripts/ensure_local_env.py --enable-espn-historical-stats

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  COMPOSE_BIN=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_BIN=(docker-compose)
else
  echo "docker compose not found. Install Docker Desktop or docker-compose." >&2
  exit 1
fi

DB_PORT="${DB_PORT:-5433}"
API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-8080}"
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-cff_local}"
export DB_PORT
export API_PORT
export WEB_PORT
export COMPOSE_PROJECT_NAME
export DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://postgres:postgres@localhost:${DB_PORT}/collegefootballfantasy}"
export UI_BASE_URL="${UI_BASE_URL:-http://localhost:${WEB_PORT}}"
export VITE_API_BASE_URL="${VITE_API_BASE_URL:-http://localhost:${API_PORT}}"

echo "Starting postgres..."
"${COMPOSE_BIN[@]}" up -d db --remove-orphans

if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
  exit 1
fi

echo "Syncing dependencies..."
uv sync

if ! command -v npm >/dev/null 2>&1; then
  echo "npm not found. Install Node.js to run the React UI." >&2
  exit 1
fi

if [ ! -d web/node_modules ]; then
  echo "Installing web dependencies..."
  npm --prefix web ci
fi

echo "Running migrations..."
PYTHONPATH=. uv run alembic -c api/alembic.ini upgrade head

PROJECTION_SEASON="${PROJECTION_SEASON:-$(date +%Y)}"
PROJECTION_WEEK="${PROJECTION_WEEK:-1}"
echo "Ensuring Week ${PROJECTION_WEEK} projections..."
PYTHONPATH=. uv run python scripts/build_weekly_projections.py \
  --season "$PROJECTION_SEASON" \
  --week "$PROJECTION_WEEK" \
  --offline \
  --only-if-missing

echo "Starting API..."
PYTHONPATH=. uv run uvicorn collegefootballfantasy_api.app.main:app --host 0.0.0.0 --port "$API_PORT" &
API_PID=$!

for attempt in {1..60}; do
  if curl --fail --silent --max-time 2 "${VITE_API_BASE_URL}/health/ready" >/dev/null; then
    break
  fi
  if ! kill -0 "$API_PID" 2>/dev/null; then
    echo "FastAPI exited before it became ready." >&2
    exit 1
  fi
  sleep 1
done

if ! curl --fail --silent --max-time 2 "${VITE_API_BASE_URL}/health/ready" >/dev/null; then
  echo "FastAPI did not become ready at ${VITE_API_BASE_URL}/health/ready." >&2
  exit 1
fi

echo "FastAPI is ready. Starting UI..."
npm --prefix web run dev:vite -- --host 0.0.0.0 --port "$WEB_PORT" &
UI_PID=$!

echo "API -> http://localhost:${API_PORT}"
echo "UI  -> http://localhost:${WEB_PORT}"

trap 'kill "$API_PID" "$UI_PID"' EXIT
while kill -0 "$API_PID" 2>/dev/null && kill -0 "$UI_PID" 2>/dev/null; do
  sleep 1
done

if ! kill -0 "$API_PID" 2>/dev/null; then
  echo "FastAPI stopped; closing the paired UI process." >&2
  exit 1
fi

echo "UI stopped; closing FastAPI." >&2
