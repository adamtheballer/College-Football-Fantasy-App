# Production Operations Runbook

This app is not public-launch ready until the checks in this runbook are wired into the real hosting environment and exercised in staging.

## Runtime Processes

Run production as separate processes:

1. **API**: FastAPI via `collegefootballfantasy_api.app.main:app`.
2. **Web**: static Vite build from `web/dist/spa`.
3. **Scoring worker**: `scripts/run_scoring_worker.py`.
4. **Trade processor**: `scripts/process_due_trades.py`.
5. **Notification worker**: `scripts/send_scheduled_notifications.py`, when scheduled notifications are enabled.

Do not run scoring inside the web process. Scoring must survive API deploys, retry safely, and expose failures in `scoring_runs`.

## Scoring Provider Policy

- `SCORING_PROVIDER=sportsdata` is the default production provider setting.
- ESPN/cache/mock providers are unofficial for production scoring unless explicitly enabled with `SCORING_ALLOW_UNOFFICIAL_PROVIDERS=true`.
- If unofficial providers are used in staging, disclose that scores are test-only and do not market the environment as public scoring.
- Provider failures must create failed or dead-letter scoring run records. Provider empty responses must not overwrite valid scores with false zeroes.

## Worker Cadence

Recommended schedules:

- Game window: every 30–90 seconds with `--mode live`.
- Postgame reconciliation: every 10–30 minutes with `--mode postgame`.
- Next-day correction sweep: hourly or once after provider finalization with `--mode correction`.
- Due trade processing: every 5–15 minutes, and once shortly after Monday reset, with `scripts/process_due_trades.py`.

Examples:

```bash
PYTHONPATH=. uv run python scripts/run_scoring_worker.py --season 2026 --week 1 --mode live
PYTHONPATH=. uv run python scripts/run_scoring_worker.py --season 2026 --week 1 --mode postgame
PYTHONPATH=. uv run python scripts/run_scoring_worker.py --season 2026 --week 1 --mode correction --once
PYTHONPATH=. uv run python scripts/process_due_trades.py
```

Retry controls:

- `SCORING_WORKER_RETRY_MAX_ATTEMPTS`
- `SCORING_WORKER_RETRY_BASE_SECONDS`
- `SCORING_DEAD_LETTER_AFTER_FAILURES`

## Health and Readiness

- `/health` is liveness only.
- `/health/ready` checks database connectivity and Alembic revision readiness.
- Do not route production traffic until `/health/ready` returns `200`.
- Admin scoring provider health is available from `/admin/scoring/provider-health` for admins.

## Migration Deployment

1. Put the release in maintenance mode if the migration is not backwards-compatible.
2. Back up the database.
3. Run `PYTHONPATH=. uv run alembic -c api/alembic.ini upgrade head`.
4. Run `PYTHONPATH=. uv run python scripts/check_alembic_head.py`.
5. Start the API.
6. Confirm `/health/ready`.
7. Start or resume workers.

Rollback rule: rollback code first only if the database migration is backwards-compatible. If not, restore from the backup or run an explicitly reviewed downgrade in staging first.

## Backup and Restore

Minimum production requirement:

- Daily full database backup.
- Point-in-time recovery when supported by the managed database.
- Monthly restore drill into an isolated staging database.

Restore drill:

1. Restore latest backup into staging.
2. Run readiness checks.
3. Run scoring smoke tests for one league/week.
4. Confirm no production secrets are exposed in staging logs.

## Incident Response

### Provider Outage

1. Stop live scoring workers if provider responses are malformed or empty.
2. Confirm `scoring_runs` contains failed/dead-letter entries.
3. Notify commissioners that scoring is delayed.
4. Resume workers only after provider health is stable.
5. Run postgame reconciliation after recovery.

### Scoring Correction

1. Preview correction in admin scoring tools.
2. Verify affected league IDs.
3. Apply correction with a reason.
4. Confirm audit row has before and after state.
5. Reconcile affected league/week standings.

### Bad Deployment

1. Disable traffic to the new API version.
2. Keep workers stopped until data integrity is confirmed.
3. Roll back to the previous known-good artifact.
4. Confirm `/health/ready`.
5. Run smoke tests for auth, league creation, draft, roster, scoring, and admin health.

## Monitoring and Alerts

Minimum alerts before public beta:

- `/health/ready` non-200.
- Any `scoring_runs.status in ('failed', 'dead_letter')`.
- High unmatched provider row rate above `PROVIDER_UNMATCHED_FAILURE_THRESHOLD_PERCENT`.
- Email delivery failures.
- Login/signup rate-limit spikes.
- Worker heartbeat missing during a scheduled game window.

## Security Checklist

- `ENVIRONMENT=production`.
- Non-default `JWT_SECRET_KEY`.
- HTTPS-only production CORS origins.
- `REFRESH_COOKIE_SECURE=true`.
- SMTP configured for verification/password reset.
- Legal/support URLs configured.
- No real secrets committed.
- Admin endpoints require verified admin users.
- Access logs redact auth and cookie headers.
