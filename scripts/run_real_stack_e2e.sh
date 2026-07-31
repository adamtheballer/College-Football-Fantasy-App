#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-cff_real_e2e}"
# Let Docker choose host ports for the isolated stack unless a caller explicitly
# supplies one. GitHub-hosted runners can already have arbitrary high ports in
# use, so fixed host bindings make this E2E job flaky for reasons unrelated to
# the application under test.
export DB_PORT="${DB_PORT:-0}"
export API_PORT="${API_PORT:-0}"
export WEB_PORT="${WEB_PORT:-0}"

cleanup() {
  docker compose down -v --remove-orphans
}
trap cleanup EXIT

docker compose down -v --remove-orphans || true
docker compose up --build -d

resolve_host_port() {
  local service="$1"
  local container_port="$2"
  local binding

  binding="$(docker compose port "$service" "$container_port" | head -n 1)"
  if [[ "$binding" =~ :([0-9]+)$ ]]; then
    printf '%s\n' "${BASH_REMATCH[1]}"
    return 0
  fi

  echo "Unable to resolve the host port for ${service}:${container_port}: ${binding}" >&2
  return 1
}

api_host_port="$(resolve_host_port api 8000)"
web_host_port="$(resolve_host_port web 8080)"

for _attempt in $(seq 1 60); do
  if curl --fail --silent --max-time 3 "http://127.0.0.1:${api_host_port}/health/ready" >/dev/null && \
    curl --fail --silent --max-time 3 --head "http://127.0.0.1:${web_host_port}" >/dev/null; then
    break
  fi
  sleep 2
done

curl --fail --show-error --silent "http://127.0.0.1:${api_host_port}/health/ready" >/dev/null
curl --fail --show-error --silent --head "http://127.0.0.1:${web_host_port}" >/dev/null

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
