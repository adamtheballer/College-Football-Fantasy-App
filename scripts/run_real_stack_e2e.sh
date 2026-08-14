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
export WEB_PORT="${WEB_PORT:-0}"
# The E2E stack is deliberately isolated from any user-provided beta dataset.
# These secrets are CI-only and the fixture script below writes only keyed HMACs.
export BETA_ACCESS_ENABLED="true"
export VITE_BETA_ACCESS_ENABLED="true"
export BETA_ACCESS_CODE_HMAC_SECRET="${BETA_ACCESS_CODE_HMAC_SECRET:-ci-only-beta-access-code-hmac-secret-2026}"
export BETA_ACCESS_RESERVATION_SECRET="${BETA_ACCESS_RESERVATION_SECRET:-ci-only-beta-access-reservation-secret-2026}"
export CFF_GIT_SHA="${CFF_GIT_SHA:-$(git rev-parse HEAD)}"
export CFF_GIT_BRANCH="${CFF_GIT_BRANCH:-$(git branch --show-current || printf 'detached')}"
# The runtime compatibility gate requires all three service identities. Keep
# this disposable stack on the same committed artifact identity as the beta
# release rather than letting the API defaults report unknown web/worker SHAs.
export CFF_WEB_GIT_SHA="${CFF_WEB_GIT_SHA:-$CFF_GIT_SHA}"
export CFF_WORKER_GIT_SHA="${CFF_WORKER_GIT_SHA:-$CFF_GIT_SHA}"
export CFF_RUNTIME_MODE="${CFF_RUNTIME_MODE:-release_candidate}"
export ENVIRONMENT="${ENVIRONMENT:-e2e}"
# This is a bounded test-only capability: the API rejects it unless its
# environment is explicitly e2e, and it is used only to advance a deferred
# trade to its canonical legal processing instant.
export E2E_LIFECYCLE_TIME_TRAVEL_ENABLED="${E2E_LIFECYCLE_TIME_TRAVEL_ENABLED:-true}"
export CFF_RUNTIME_ID="${CFF_RUNTIME_ID:-e2e-${CFF_GIT_SHA:0:12}}"
# The disposable browser/lifecycle stack must exercise the beta provider
# policy without credentials or outbound SportsData polling.
export SCORING_MODE="${SCORING_MODE:-disabled}"
export SPORTSDATA_ENABLED="${SPORTSDATA_ENABLED:-false}"
export EMAIL_ENABLED="${EMAIL_ENABLED:-false}"
# The E2E stack is a fresh disposable database. Its catalog must be created by
# the explicit all-or-nothing reconciler, never by ordinary runtime startup.
export CFF_APPLY_PRESEASON_RECONCILIATION="true"

cleanup() {
  local exit_status=$?
  if (( exit_status != 0 )); then
    # `down -v` intentionally leaves no disposable database behind. Preserve
    # the API's startup failure immediately before that cleanup so an E2E
    # failure is diagnosable instead of appearing as an unexplained unhealthy
    # dependency in CI output.
    docker compose ps >&2 || true
    docker compose logs --no-color --tail 200 api >&2 || true
  fi
  docker compose down -v --remove-orphans
  exit "$exit_status"
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

web_host_port="$(resolve_host_port web 8080)"
if ! [[ "$web_host_port" =~ ^[1-9][0-9]*$ ]] || (( web_host_port > 65535 )); then
  echo "Unable to resolve a usable host port for web:8080; refusing to probe an invalid port." >&2
  exit 1
fi

web_origin="http://127.0.0.1:${web_host_port}"

for _attempt in $(seq 1 60); do
  if curl --fail --silent --max-time 3 "${web_origin}/api/health/ready" >/dev/null && \
    curl --fail --silent --max-time 3 "${web_origin}/api/health/runtime" >/dev/null && \
    curl --fail --silent --max-time 3 --head "${web_origin}" >/dev/null; then
    break
  fi
  sleep 2
done

ready_payload="$(curl --fail --show-error --silent "${web_origin}/api/health/ready")"
runtime_payload="$(curl --fail --show-error --silent "${web_origin}/api/health/runtime")"
jq -e '.status == "ready"' <<<"$ready_payload" >/dev/null
jq -e --arg sha "$CFF_GIT_SHA" '.git_sha == $sha and .alembic_revision == "0090_expand_league_icon_url" and .scoring_mode == "disabled" and .sportsdata_enabled == false and .provider_polling_expected == false and .email_enabled == false' <<<"$runtime_payload" >/dev/null
curl --fail --show-error --silent --head "${web_origin}" >/dev/null

# This command runs only after Compose created a fresh disposable database.
# It never accepts, reads, or logs a real invitation code.
docker compose exec -T api env CFF_SEED_CI_BETA_ACCESS_FIXTURES=1 \
  PYTHONPATH=/app uv run python scripts/seed_ci_beta_access_fixtures.py

for _attempt in $(seq 1 30); do
  if docker compose exec -T db psql -U postgres -d collegefootballfantasy -Atc \
    "select status from worker_heartbeats where worker_name = 'lifecycle_processor'" | grep -qx "healthy"; then
    break
  fi
  sleep 2
done

docker compose exec -T db psql -U postgres -d collegefootballfantasy -Atc \
  "select status from worker_heartbeats where worker_name = 'lifecycle_processor'" | grep -qx "healthy"

# Exercise the actual Postgres-backed lifecycle processors at a legal future
# processing instant.  The browser trade test below proves the public pending
# cards; this stress fixture proves that the canonical due-trade path advances
# a deferred offer exactly once, moves both players atomically, and leaves no
# duplicate waiver or draft award when concurrent workers race.
docker compose exec -T api \
  PYTHONPATH=/app uv run python scripts/stress_lifecycle_workers.py

# The E2E service is profile-gated, so `up --build` above does not build it.
# Build it explicitly to ensure Playwright always exercises the current source
# rather than a stale locally cached test image.
docker compose --profile e2e build e2e
docker compose --profile e2e run --rm --no-deps e2e
