#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
echo "checkout=$ROOT_DIR"
echo "branch=$(git -c core.fsmonitor=false branch --show-current)"
echo "sha=$(git -c core.fsmonitor=false rev-parse HEAD)"
echo "compose_project=cff_beta"
echo "url=http://127.0.0.1:18080"
docker compose -p cff_beta -f docker-compose.yml -f docker-compose.beta-local.yml ps
curl --fail --silent --max-time 5 http://127.0.0.1:18080/api/health/ready
curl --fail --silent --max-time 5 http://127.0.0.1:18080/api/health/runtime
