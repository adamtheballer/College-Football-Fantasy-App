# Local ESPN historical imports

The ESPN historical importer is intentionally manual. Enabling it permits the import command and refresh jobs to call ESPN; it does not automatically scrape every player when the API starts.

## Prepare a worktree

Each Git worktree has its own ignored `.env` file. Run this once from the worktree that starts the API:

```bash
make env
```

This creates `.env` from `.env.example` when missing and sets `ESPN_HISTORICAL_STATS_ENABLED=true` without printing or replacing other local values. `make dev` and `make bootstrap` run the same setup automatically.

## Import data

The historical import is a two-stage job. It first resolves missing ESPN identities and persists the validated athlete profile, then imports historical seasons for every successfully mapped player. Resolution only accepts an exact name, school, and position match; it does not overwrite internal `cfb27:` identifiers.

```bash
PYTHONPATH=. uv run python scripts/import_espn_historical_stats.py --dry-run
PYTHONPATH=. uv run python scripts/import_espn_historical_stats.py --limit 25
```

The preflight reports the players that already have trusted mappings and the players that will receive safe identity lookups. Use `--skip-identity-resolution` only when you intentionally want to import existing mappings without attempting a safe lookup.

The standalone identity command remains useful when you want to backfill mappings without importing stats:

```bash
PYTHONPATH=. uv run python scripts/sync_espn_player_identities.py --dry-run
PYTHONPATH=. uv run python scripts/sync_espn_player_identities.py
```

Use `--dry-run` to see the importer plan without making ESPN calls or writing data.

Each completed run reports players scanned, already/newly mapped, ambiguous, not found, profile rows updated, historical-stat successes, and failures. Ambiguous and not-found identities are stored as auditable unmatched provider rows instead of being silently skipped.

For an intentional one-off import while the feature flag is disabled, use `--ignore-feature-flag`. The override reaches the historical-stat service itself; it does not bypass identity validation, profile matching, or audit records.

## Why worktrees can look empty

Docker Compose now defaults to the stable `cff_local` project, so ordinary worktrees reuse the `cff_local_pgdata` volume. A worktree does not create a new database by itself. A different database is created only when you intentionally override `COMPOSE_PROJECT_NAME` or remove the volume with `docker compose down -v`.

For the normal development stack, keep a stable project name and do not use `down -v`:

```bash
docker compose up -d
```

Use a disposable project name and `down -v` only for isolated test stacks:

```bash
COMPOSE_PROJECT_NAME=cff_test docker compose up -d
COMPOSE_PROJECT_NAME=cff_test docker compose down -v
```

## Docker configuration

The Compose API service receives `ESPN_HISTORICAL_STATS_ENABLED` and the historical importer settings explicitly. Recreate the API container after changing `.env`:

```bash
docker compose up -d --build api
```
