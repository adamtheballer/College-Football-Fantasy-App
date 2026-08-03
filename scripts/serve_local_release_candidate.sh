#!/usr/bin/env bash
set -euo pipefail

# Compatibility shim for the former release-candidate launcher.  The old
# implementation created a commit-named Compose project and therefore a new,
# empty database volume while still publishing the UI at 18080.  That made the
# browser appear to lose leagues and beta-access data.  All beta starts now
# use the fixed cff_beta project, one public origin, and an explicit existing
# data volume.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
echo "serve_local_release_candidate.sh is retired; starting the fixed beta runtime instead." >&2
exec scripts/start-beta-local.sh "$@"
