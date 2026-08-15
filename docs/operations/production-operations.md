# Production Operations Runbook

This app is not public-launch ready until the checks in this runbook are wired into the real hosting environment and exercised in staging.

## Runtime Processes

Run production as separate processes:

1. **API**: FastAPI via `collegefootballfantasy_api.app.main:app`.
2. **Web**: static Vite build from `web/dist/spa`.
3. **Scoring worker**: `scripts/run_scoring_worker.py`.
4. **Lifecycle worker**: `scripts/run_lifecycle_worker.py`; processes expired draft picks, due waiver windows, and due or expired trade offers.
5. **Notification worker**: `scripts/run_notification_worker.py`; claims and delivers the durable notification outbox.

Do not run scoring inside the web process. Scoring must survive API deploys, retry safely, and expose failures in `scoring_runs`.

Do not omit the lifecycle worker in production. Without it, draft clocks do not auto-pick, approved waiver windows do not clear, and due trades do not advance.

The notification worker is deliberately independent of both the API request path and the scoring worker. A provider outage must never roll back a trade, waiver, draft, chat, or roster transaction.

## Notification Delivery Configuration

In-app history is always produced by the durable outbox. Push and email are opt-in, disabled by default, and are processed only by the notification worker.

- OneSignal push: set `PUSH_NOTIFICATIONS_ENABLED=true`, `PUSH_PROVIDER=onesignal`, `ONESIGNAL_APP_ID`, and `ONESIGNAL_APP_API_KEY` in the notification-worker secret store. The server key must not be present in API browser configuration or Vite variables.
- Web push: pass only `VITE_ONESIGNAL_APP_ID` at web build time. The site must use HTTPS, serve `OneSignalSDKWorker.js` from the same origin, and prompt only after the user presses **Enable push notifications** in Settings.
- Resend email: set `EMAIL_ENABLED=true`, `EMAIL_DELIVERY_MODE=resend`, `RESEND_API_KEY`, and `RESEND_FROM` in the notification-worker secret store. SMTP remains reserved for the existing auth-email path.
- Live player-update fanout remains disabled with `LIVE_PLAYER_NOTIFICATIONS_ENABLED=false` until an authoritative data provider and runbook are approved. This setting does not affect draft, trade, waiver, or in-app notification processing.

The worker writes the provider result, retry schedule, and provider message ID to `notification_delivery_attempts`. It uses deterministic provider idempotency keys; a retry after a worker crash may repeat a provider request only with that same idempotency key. Never mark a notification sent merely because it was queued.

## Scoring Provider Policy

- Live scoring is disabled by default (`SCORING_MODE=disabled`). A production rollout must explicitly set `SCORING_MODE=enabled` and configure its approved provider; when enabled, `SCORING_PROVIDER=sportsdata` is the standard provider setting.
- ESPN/cache/mock providers are unofficial for production scoring unless explicitly enabled with `SCORING_ALLOW_UNOFFICIAL_PROVIDERS=true`.
- If unofficial providers are used in staging, disclose that scores are test-only and do not market the environment as public scoring.
- Provider failures must create failed or dead-letter scoring run records. Provider empty responses must not overwrite valid scores with false zeroes.

## Worker Cadence

Recommended schedules:

- Game window: every 30–90 seconds with `--mode live`.
- Postgame reconciliation: every 10–30 minutes with `--mode postgame`.
- Next-day correction sweep: hourly or once after provider finalization with `--mode correction`.
- Lifecycle processing: every 5–15 minutes (or the configured lifecycle interval) with `scripts/run_lifecycle_worker.py`. It must remain active through draft windows, waiver-clear windows, and trade review windows.
- Notification processing: continuously, or every `NOTIFICATION_WORKER_INTERVAL_SECONDS` (default five seconds), with `scripts/run_notification_worker.py`. Retry attempts use bounded backoff and stop after `NOTIFICATION_MAX_ATTEMPTS`.

Examples:

```bash
PYTHONPATH=. uv run python scripts/run_scoring_worker.py --season 2026 --week 1 --mode live
PYTHONPATH=. uv run python scripts/run_scoring_worker.py --season 2026 --week 1 --mode postgame
PYTHONPATH=. uv run python scripts/run_scoring_worker.py --season 2026 --week 1 --mode correction --once
PYTHONPATH=. uv run python scripts/run_lifecycle_worker.py
PYTHONPATH=. uv run python scripts/run_notification_worker.py
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
- The notification-worker heartbeat records its queue counts and the last successful delivery time. Alert if the heartbeat is stale, failures accumulate, or retries remain nonzero beyond the retry window.

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

### Notification Provider Outage

1. Leave the notification worker and database running so in-app history continues to be recorded.
2. Disable external delivery with `PUSH_NOTIFICATIONS_ENABLED=false` and/or `EMAIL_ENABLED=false` if the provider is rejecting requests broadly.
3. Inspect `notification_delivery_attempts` and the `notification_processor` heartbeat for failed and retrying events; do not copy provider request payloads or subscription IDs into tickets.
4. Re-enable the channel only after a staging smoke test confirms a provider acceptance result and a valid deep link.
5. Reprocess only the bounded failed/retry events approved by the incident owner; preserve event keys so provider idempotency still applies.

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
- Notification worker heartbeat missing, nonzero retry backlog beyond the backoff window, or a growing failed notification count.
- Login/signup rate-limit spikes.
- Worker heartbeat missing during a scheduled game window.

## Security Checklist

- `ENVIRONMENT=production`.
- Non-default `JWT_SECRET_KEY`.
- HTTPS-only production CORS origins.
- `REFRESH_COOKIE_SECURE=true`.
- SMTP configured for verification/password reset.
- OneSignal server credentials and Resend credentials exist only in the notification worker's secret scope; the browser receives only the public OneSignal app ID.
- Legal/support URLs configured.
- No real secrets committed.
- Admin endpoints require verified admin users.
- Access logs redact auth and cookie headers.
