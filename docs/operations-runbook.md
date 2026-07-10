# Operations, Observability, Backup, and Rollback Runbook

## Production Signals

Use these endpoints to diagnose issues without direct database access:

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Process liveness. |
| `GET /health/ready` | Database and Alembic readiness with DB latency. |
| `GET /admin/ops/metrics` | Request metrics, failed jobs, stale provider cache, pending waivers, open trades. |
| `GET /admin/ops/failed-jobs` | Failed scoring runs and provider sync jobs. |
| `GET /admin/ops/audit-events` | Audit log search by league, actor, action, entity, or request ID. |
| `GET /admin/ops/users/{user_id}/security` | User login/session/security diagnostics. |
| `GET /admin/ops/leagues/{league_id}/diagnostics` | League teams, members, scoring runs, and audit trail. |
| `GET /admin/scoring/runs` | Scoring worker telemetry. |
| `docs/SCORING_PRODUCTION_RUNBOOK.md` | Live scoring worker cadence, alerts, and incident runbook. |
| `GET /admin/provider-sync/status` | Provider freshness and sync history. |

Every response includes `X-Request-ID`. Logs include `request_id`, `user_id`, `league_id`, route, status, latency, and error code.

## Alerting Targets

Alert on:

- `/health/ready` returning non-200.
- `5xx` request rate above normal baseline.
- Any failed or partial scoring run during game windows.
- Any failed provider sync job during game windows.
- Stale provider state for live scoring feeds.
- High unmatched provider-row rate.
- Pending waiver claims past expected processing time.
- Open trade offers stuck in `accepted` or `commissioner_review`.

## Daily Postgres Backup

Recommended managed Postgres settings:

- Daily automated snapshot with at least 7 days retention.
- Point-in-time recovery enabled if supported.
- Pre-deploy manual snapshot before migrations.
- Separate staging and production databases.

Manual backup example:

```bash
pg_dump "$DATABASE_URL" --format=custom --file "backups/cff-$(date +%Y%m%d-%H%M%S).dump"
```

## Restore Drill

Run a restore drill at least monthly against a non-production database:

```bash
createdb cff_restore_drill
pg_restore --clean --if-exists --dbname cff_restore_drill backups/latest.dump
PYTHONPATH=. uv run alembic -c api/alembic.ini upgrade head
PYTHONPATH=. uv run python scripts/check_alembic_head.py
```

Then smoke test:

```bash
curl -f http://localhost:8000/health
curl -f http://localhost:8000/health/ready
```

## Pre-Migration Backup

Before production migrations:

1. Confirm staging migration check passed.
2. Take a production snapshot.
3. Record current app image/commit SHA.
4. Run migrations once.
5. Confirm `/health/ready` returns `ready`.
6. Deploy app using the same commit SHA.

## Rollback Plan

If deploy fails before migrations:

1. Roll back app image to previous SHA.
2. Confirm `/health` and `/health/ready`.

If deploy fails after migrations:

1. Stop write traffic if data corruption is possible.
2. Prefer forward-fix migration if the schema is compatible.
3. If not compatible, restore pre-migration snapshot to a new database.
4. Point app to restored database.
5. Roll back app image to previous SHA.
6. Verify `/health/ready`, auth login, league read, scoring run list, and provider status.

Do not run ad hoc destructive SQL in production without a fresh backup and written rollback notes.
