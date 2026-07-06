# Scoring Production Runbook

This app scores through backend workers only:

```txt
provider stats -> player_stats -> scoring engine -> player/team week scores -> matchups -> standings -> frontend polling
```

Do not poll ESPN, SportsData, or Google Sheets directly from the frontend.

## Worker Command

Run the live worker every 30-90 seconds during game windows:

```bash
PYTHONPATH=. uv run python scripts/sync_live_scores.py --provider espn --season 2026 --week 1 --watch --interval-seconds 90 --max-attempts 3 --backoff-seconds 2
```

For a single league:

```bash
PYTHONPATH=. uv run python scripts/sync_live_scores.py --provider espn --league-id 1 --season 2026 --week 1 --watch --interval-seconds 90
```

## Health Check

Use this from a monitor or scheduler after worker execution:

```bash
PYTHONPATH=. uv run python scripts/check_scoring_health.py --provider espn --season 2026 --week 1 --max-age-seconds 180
```

Exit codes:

```txt
0 OK
1 warning/stale/running
2 critical/missing/failed
```

## Required Alerts

Alert on:

- latest run status is `failed`
- latest successful run is older than 180 seconds during a game window
- `rows_unmatched > 0` for fantasy-relevant players
- `retry_count > 0` repeatedly
- `rows_fetched = 0` while games are live
- scoring job lock remains active past its TTL

## Admin Reconciliation

Admin-only endpoints:

```txt
GET  /admin/scoring/runs
GET  /admin/scoring/runs/{run_id}
GET  /admin/scoring/leagues/{league_id}/weeks/{week}?season=2026
GET  /admin/scoring/players/{player_id}/weeks/{week}?season=2026&league_id=1
GET  /admin/scoring/unmatched-provider-rows
GET  /admin/scoring/provider-identity
POST /admin/scoring/leagues/{league_id}/weeks/{week}/finalize?season=2026
POST /admin/scoring/leagues/{league_id}/weeks/{week}/stat-corrections?season=2026
```

Use these to trace:

```txt
raw provider row -> normalized stats -> scoring rules -> player score -> team score -> matchup score -> standings
```

## Stat Corrections

Corrections must be auditable. Use the stat correction endpoint rather than editing scores directly. The correction flow:

```txt
update player_stats -> recalculate league week -> mark matchups stat_corrected -> recalculate standings -> write scoring_correction_audits
```

## Roster Locks

Roster moves are blocked after a player school’s game kicks off for the active scoring week. Before kickoff, a manager can still move/drop/add the player.

## Known Production Gaps

- ESPN is acceptable for internal alpha/fallback only; production should use an official provider contract.
- Frontend trust states show stale/provider-down conditions from polling state, but richer backend freshness fields should be added later.
- Admin reconciliation is API-first; a dedicated admin UI can be built on top of the endpoints.
