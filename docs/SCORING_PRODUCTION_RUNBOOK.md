# Scoring Production Runbook

This app scores through backend workers only:

```txt
provider stats -> player_stats -> scoring engine -> player/team week scores -> matchups -> standings -> frontend polling
```

Do not poll ESPN, SportsData, or Google Sheets directly from the frontend. GitHub Actions ingestion is acceptable for reference-data refreshes and daily backfills only; it is not the production live-scoring scheduler.

## Production Architecture

Run scoring as a separate long-lived worker process or managed scheduled worker, not inside the web process.

```txt
web/API service
  serves users, admin scoring views, health endpoints

scoring-live worker
  runs during active game windows every 30-90 seconds
  calls scripts/sync_live_scores.py with --watch
  updates raw stats, fantasy scores, matchups, standings

scoring-postgame worker
  runs after game windows every 10-30 minutes
  catches late stat updates and provider lag

scoring-final-sweep worker
  runs next morning and again before standings lock
  performs correction sweep/finalization review

monitoring/alerting
  checks /health/ready, /admin/scoring/runs, provider freshness, failed jobs, unmatched rows
```

Only one scoring worker may run for a given `provider + season + week + league_id` key. The backend `scoring_job_locks` table enforces this, but deployment should still avoid intentionally overlapping schedules.

## Worker Commands

Live game-window worker, all leagues for the week:

```bash
PYTHONPATH=. uv run python scripts/sync_live_scores.py \
  --provider sportsdata \
  --season 2026 \
  --week 1 \
  --watch \
  --interval-seconds 60 \
  --max-attempts 3 \
  --backoff-seconds 2 \
  --lock-ttl-seconds 300 \
  --stale-run-seconds 900 \
  --worker-id scoring-live-sportsdata-2026-w1
```

Single-league isolation command:

```bash
PYTHONPATH=. uv run python scripts/sync_live_scores.py \
  --provider sportsdata \
  --league-id 1 \
  --season 2026 \
  --week 1 \
  --watch \
  --interval-seconds 60 \
  --worker-id scoring-live-league-1-2026-w1
```

One-shot postgame/correction command:

```bash
PYTHONPATH=. uv run python scripts/sync_live_scores.py \
  --provider sportsdata \
  --season 2026 \
  --week 1 \
  --max-attempts 5 \
  --backoff-seconds 5 \
  --worker-id scoring-postgame-sportsdata-2026-w1
```

Provider choice:

- `sportsdata` should be the production provider when an official provider contract and API key are available.
- `espn` is internal-alpha/fallback only unless product/legal approves it for production use.

## Deployment Cadence

Use a scheduler that supports protected environment secrets, retries, and alert hooks. Good options: managed worker service plus cron/scheduler, Kubernetes CronJobs plus a Deployment for live windows, Render/Railway/Fly worker processes, ECS scheduled tasks, or a dedicated process supervisor.

| Window | Cadence | Command Mode | Purpose |
| --- | ---: | --- | --- |
| Pregame, 30 min before first kickoff | every 5 min | one-shot | verify provider reachable, populate initial telemetry |
| During live games | every 30-90 sec | `--watch` or frequent one-shot | keep matchups current |
| Halftime/late slate overlap | every 30-60 sec | `--watch` | higher freshness when many games active |
| Postgame, 0-4 hours after last game | every 10-30 min | one-shot | capture delayed provider corrections |
| Next day final sweep | 2-3 scheduled runs | one-shot | catch final stat corrections before standings lock |
| Offseason/no games | disabled except manual backfill | one-shot | avoid needless provider calls |

Default production interval should be 60 seconds during live windows. Drop to 30 seconds only if provider limits and database load are verified. Use 90 seconds if provider rate limits or cost require it.

## Game-Window Schedule

The scheduler should be driven by the persisted `games` table or provider schedule feed, not a hardcoded weekly cron.

Required schedule logic:

1. Identify games for `season + week` with kickoff times.
2. Start the live worker 30 minutes before the first relevant kickoff.
3. Keep it running until 30 minutes after the last game window ends.
4. If game final statuses are available, transition from live cadence to postgame cadence when all games are final.
5. If final statuses are unavailable, use kickoff plus a conservative duration window, then postgame cadence.
6. Disable live cadence for weeks with no scheduled games.

The daily ESPN ingestion Action must not be used as the live cadence source. It can refresh schedules, rankings, and reference data, but live scoring requires this separate worker plan.

## Environment and Secrets

Run the worker in a protected production environment. Do not expose provider keys or production DB credentials to frontend builds or unprotected CI jobs.

Required secrets:

```txt
DATABASE_URL
JWT_SECRET_KEY
SPORTSDATA_API_KEY or approved production provider key
SPORTSDATA_ENABLED=true when using SportsData
CORS_ORIGINS
UI_BASE_URL
```

Recommended environment controls:

- Separate `production` and `staging` environments.
- Manual approval required before production secret changes.
- Worker service uses least-privilege production DB credentials where possible.
- Provider API keys are read by the worker/API only, never by React.
- Scheduled jobs run from the same release image/commit as the API.
- Migrations run before worker deployment, not independently inside every worker loop.

## Retry and Backoff

The scoring worker already supports provider retry and job locking. Production settings should be conservative:

```txt
--max-attempts 3 during live windows
--backoff-seconds 2 during live windows
--max-attempts 5 during postgame/final sweeps
--backoff-seconds 5 during postgame/final sweeps
--lock-ttl-seconds 300
--stale-run-seconds 900
```

Rules:

- Do not overwrite existing scores when the provider returns zero rows for a week with matchups.
- Treat repeated `rows_fetched = 0` during live windows as an alert, not success.
- Treat provider errors as retryable until attempts are exhausted.
- Let `scoring_job_locks` prevent overlap; do not manually clear locks unless the worker is confirmed dead.
- If a provider outage lasts more than 10 minutes during games, show stale/live-unavailable state in the UI and keep polling at the safe interval.

## Health Checks

Run this after worker execution from monitoring or a scheduler hook:

```bash
PYTHONPATH=. uv run python scripts/check_scoring_health.py \
  --provider sportsdata \
  --season 2026 \
  --week 1 \
  --max-age-seconds 180
```

Exit codes:

```txt
0 OK
1 warning/stale/running
2 critical/missing/failed
```

Admin-only endpoints for investigation:

```txt
GET  /admin/scoring/runs
GET  /admin/scoring/runs/{run_id}
GET  /admin/scoring/leagues/{league_id}/weeks/{week}?season=2026
GET  /admin/scoring/players/{player_id}/weeks/{week}?season=2026&league_id=1
GET  /admin/scoring/unmatched-provider-rows
POST /admin/scoring/unmatched-provider-rows/{row_id}/map
POST /admin/scoring/unmatched-provider-rows/{row_id}/ignore
POST /admin/scoring/unmatched-provider-rows/{row_id}/resolve
GET  /admin/scoring/provider-identity
POST /admin/scoring/leagues/{league_id}/weeks/{week}/finalize?season=2026
POST /admin/scoring/leagues/{league_id}/weeks/{week}/stat-corrections?season=2026
```

Use these to trace:

```txt
raw provider row -> provider identity mapping -> normalized stats -> scoring rules -> player score -> team score -> matchup score -> standings
```

## Alerts

Page immediately during live game windows:

- `/health/ready` returns non-200.
- Latest scoring run status is `failed`.
- Latest successful run is older than 180 seconds during live cadence.
- `rows_fetched = 0` while games are live.
- `rows_unmatched > 0` for fantasy-relevant players.
- `retry_count > 0` for 3 consecutive runs.
- Scoring job lock remains active past TTL.
- Provider API returns rate-limit, auth, or quota errors.
- Matchups are stale while frontend indicates games are live.

Warn, but do not page, outside live game windows:

- Postgame run delayed more than 30 minutes.
- Final sweep missing by next-day cutoff.
- Open unmatched provider rows remain unresolved after sweep.
- Provider sync state stale for schedule/injury/reference feeds.

## Incident Runbook

### Live scores are stale

1. Check `/health/ready`.
2. Check latest `/admin/scoring/runs?provider=sportsdata&season=<year>&week=<week>`.
3. Confirm worker process is running and using the expected release SHA.
4. Confirm `DATABASE_URL` and provider key are present in the worker environment.
5. Run one-shot worker manually for the affected week.
6. Run `scripts/check_scoring_health.py`.
7. If provider is down, keep worker polling and communicate stale-state status.

### Worker is stuck running

1. Inspect active `scoring_job_locks` through admin failed-jobs/DB diagnostics.
2. Confirm whether the worker process still exists.
3. If process is dead and lock TTL has elapsed, run a new one-shot worker; stale recovery should mark old runs stale.
4. Do not delete locks manually unless stale recovery fails and a fresh DB backup exists.

### Provider identity mismatch

1. Open `/admin/scoring/unmatched-provider-rows`.
2. Map provider rows to players using `/map` when confident.
3. Ignore non-fantasy or invalid provider rows using `/ignore`.
4. Re-run one-shot scoring for the affected week.
5. Verify `/admin/scoring/provider-identity` has no fantasy-relevant gaps.

### Bad stat changed a matchup

1. Inspect `/admin/scoring/players/{player_id}/weeks/{week}`.
2. Apply correction through `POST /admin/scoring/leagues/{league_id}/weeks/{week}/stat-corrections`.
3. Verify recalculated player/team/matchup scores.
4. Finalize only after provider rows and corrections are reconciled.

## Stat Corrections

Corrections must be auditable. Use the stat correction endpoint rather than editing scores directly. The correction flow:

```txt
update player_stats -> recalculate league week -> mark matchups stat_corrected -> recalculate standings -> write scoring_correction_audits
```

## Roster Locks

Roster moves are blocked after a player school’s game kicks off for the active scoring week. Before kickoff, a manager can still move/drop/add the player.

## Launch Checklist

Before public launch:

- Production worker service exists separately from the API process.
- Worker runs from the same release image/commit as the API.
- Production provider contract/key is configured in protected secrets.
- Game-window scheduler is active and tested in staging.
- Live cadence is verified at 60 seconds without provider throttling.
- Postgame and next-day final sweeps are scheduled.
- Alerts are connected to the on-call channel.
- Admin can inspect scoring runs, unmatched rows, provider identity, and stat corrections.
- Runbook has current production provider, scheduler, dashboard, and on-call links.

## Known Production Gaps

- ESPN is acceptable for internal alpha/fallback only; production should use an official provider contract.
- This document defines the required deployment plan; the exact scheduler implementation depends on the production host.
- Frontend trust states should continue to surface stale/provider-down conditions from backend scoring state.
