#!/usr/bin/env bash
set -euo pipefail

# Stop only the fixed beta Compose project.  Named database volumes are never
# removed, including on failure.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
readonly ENV_FILE="${CFF_BETA_ENV_FILE:-$ROOT_DIR/.beta-runtime.env}"
docker compose --env-file "$ENV_FILE" -p cff_beta -f docker-compose.yml -f docker-compose.beta-local.yml down --remove-orphans
echo "Beta containers stopped; database volume was preserved."
