#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-cff_real_e2e}"
export DB_PORT="${DB_PORT:-55460}"
export API_PORT="${API_PORT:-55461}"
export WEB_PORT="${WEB_PORT:-55462}"

cleanup() {
  docker compose down -v --remove-orphans
}
trap cleanup EXIT

docker compose down -v --remove-orphans || true
docker compose up --build -d

for _attempt in $(seq 1 60); do
  if curl --fail --silent --max-time 3 "http://127.0.0.1:${API_PORT}/health/ready" >/dev/null && \
    curl --fail --silent --max-time 3 --head "http://127.0.0.1:${WEB_PORT}" >/dev/null; then
    break
  fi
  sleep 2
done

curl --fail --show-error --silent "http://127.0.0.1:${API_PORT}/health/ready" >/dev/null
curl --fail --show-error --silent --head "http://127.0.0.1:${WEB_PORT}" >/dev/null

for _attempt in $(seq 1 30); do
  if docker compose exec -T db psql -U postgres -d collegefootballfantasy -Atc \
    "select status from worker_heartbeats where worker_name = 'lifecycle_processor'" | grep -qx "healthy"; then
    break
  fi
  sleep 2
done

docker compose exec -T db psql -U postgres -d collegefootballfantasy -Atc \
  "select status from worker_heartbeats where worker_name = 'lifecycle_processor'" | grep -qx "healthy"

docker compose --profile e2e run --rm --no-deps e2e
