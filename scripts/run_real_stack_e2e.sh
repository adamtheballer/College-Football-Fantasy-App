#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-cff_real_e2e}"
export DB_PORT="${DB_PORT:-55460}"
export API_PORT="${API_PORT:-55461}"
export WEB_PORT="${WEB_PORT:-55462}"
REPORT_DIR="${REAL_STACK_E2E_REPORT_DIR:-$ROOT_DIR/reports/real-stack-e2e}"
E2E_CONTAINER_NAME="${COMPOSE_PROJECT_NAME}_e2e_artifacts"

mkdir -p "$REPORT_DIR"

cleanup() {
  local exit_status=$?
  docker compose logs --no-color >"$REPORT_DIR/stack.log" 2>&1 || true
  docker rm -f "$E2E_CONTAINER_NAME" >/dev/null 2>&1 || true
  docker compose down -v --remove-orphans
  return "$exit_status"
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

set +e
docker compose --profile e2e run --no-deps --name "$E2E_CONTAINER_NAME" e2e
e2e_status=$?
set -e

docker logs "$E2E_CONTAINER_NAME" >"$REPORT_DIR/e2e.log" 2>&1 || true
docker cp "$E2E_CONTAINER_NAME:/app/web/playwright-report/." "$REPORT_DIR/playwright-report" 2>/dev/null || true
docker cp "$E2E_CONTAINER_NAME:/app/web/test-results/." "$REPORT_DIR/test-results" 2>/dev/null || true
docker rm -f "$E2E_CONTAINER_NAME" >/dev/null 2>&1 || true

exit "$e2e_status"
