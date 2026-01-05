#!/usr/bin/env bash
set -euo pipefail

if ! command -v docker-compose >/dev/null 2>&1; then
  echo "docker-compose not found. Install Docker Desktop or docker-compose." >&2
  exit 1
fi

echo "Starting postgres..."
docker-compose up -d db

if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
  exit 1
fi

echo "Syncing dependencies..."
uv sync

echo "Running migrations..."
uv run alembic -c api/alembic.ini upgrade head

echo "Starting API and UI..."
uv run uvicorn collegefootballfantasy_api.app.main:app --host 0.0.0.0 --port 8000 &
API_PID=$!

uv run streamlit run ui/app.py --server.port 8501 --server.address 0.0.0.0 &
UI_PID=$!

trap 'kill "$API_PID" "$UI_PID"' EXIT
wait
