#!/usr/bin/env bash
set -euo pipefail

export DB_PORT="${DB_PORT:-5433}"
export DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://postgres:postgres@localhost:${DB_PORT}/collegefootballfantasy}"
export UI_BASE_URL="${UI_BASE_URL:-http://localhost:8080}"
export CORS_ORIGINS="${CORS_ORIGINS:-http://localhost:8080,http://127.0.0.1:8080}"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm not found. Install Node.js to run the React UI." >&2
  exit 1
fi

if [ ! -d web/node_modules ]; then
  echo "Installing web dependencies..."
  npm --prefix web install
fi

echo "Starting API and UI without Docker."
echo "This requires an existing database reachable at: ${DATABASE_URL}"
echo "If the API fails readiness, start Postgres or run: make dev"

PYTHONPATH=. uv run uvicorn api.app.main:app --host 0.0.0.0 --port 8000 --reload &
API_PID=$!

npm --prefix web run dev -- --host 0.0.0.0 --port 8080 &
UI_PID=$!

echo "API -> http://localhost:8000"
echo "UI  -> http://localhost:8080"

trap 'kill "$API_PID" "$UI_PID"' EXIT
wait
