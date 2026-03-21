#!/usr/bin/env bash
set -euo pipefail

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  COMPOSE_BIN=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_BIN=(docker-compose)
else
  echo "docker compose not found. Install Docker Desktop or docker-compose." >&2
  exit 1
fi

DB_PORT="${DB_PORT:-5433}"
export DB_PORT
export DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://postgres:postgres@localhost:${DB_PORT}/collegefootballfantasy}"

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
  npm --prefix web install
fi

echo "Running migrations..."
uv run alembic -c api/alembic.ini upgrade head

echo "Starting API and UI..."
uv run uvicorn api.app.main:app --host 0.0.0.0 --port 8000 &
API_PID=$!

npm --prefix web run dev -- --host 0.0.0.0 &
UI_PID=$!

trap 'kill "$API_PID" "$UI_PID"' EXIT
wait
