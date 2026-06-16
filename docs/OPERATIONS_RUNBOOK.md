# Operations Runbook

Use this runbook for staging, friends beta, and public launch operations. Public launch is blocked until the critical procedures below are tested.

## Daily Checks

- API `/health` returns success.
- API `/health/ready` returns database and migration readiness.
- Worker heartbeat is fresh.
- Provider sync states are fresh for active season/week data.
- Draft timeout runner has no repeated failures.
- Scoring jobs have no failed runs.
- Notification delivery errors are reviewed.

## Data Import Procedure

1. Confirm provider API keys are present only in backend/worker environments.
2. Run reference-data sync before player/stat-specific syncs.
3. Import or refresh player pool.
4. Sync schedules and game start times before roster locks.
5. Sync stats for the active week.
6. Review provider sync state and failure logs.
7. Run a small API search check for player name, school, and position.

## Weekly Scoring Procedure

1. Confirm active league week.
2. Confirm schedules and game start times are loaded.
3. Lock lineups according to game start times.
4. Sync player game stats.
5. Run scoring recompute for the week.
6. Review scoring diff and failed player rows.
7. Finalize weekly scores only after validation.
8. Update standings snapshots.
9. Record audit/admin action for commissioner-run scoring jobs.

## Stat Correction Procedure

1. Identify affected season/week/player/team rows.
2. Re-sync corrected provider data.
3. Run scoring recompute in preview mode if available.
4. Compare previous and new matchup/team scores.
5. Apply correction.
6. Recompute standings.
7. Record audit note with source and reason.

## Draft Emergency Procedure

1. Pause the draft if the room appears inconsistent.
2. Check draft room state from API.
3. Verify latest `DraftPick`, roster entries, current pick, and timer state.
4. Do not manually edit DB rows without an audit path.
5. If duplicate or partial state is detected, stop public traffic for that league and restore from backup or apply an audited repair.

## Trade/Waiver Incident Procedure

1. Freeze affected league mutations if roster corruption is suspected.
2. Compare transaction log, roster entries, trade/waiver rows, and audit actions.
3. Reject or roll back pending stale operations through service endpoints when possible.
4. Use direct database repair only with an incident record and before reopening league activity.

## Backup And Restore Drill

Public launch requires a successful restore drill:

1. Take a managed Postgres backup.
2. Restore into a separate recovery database.
3. Point a staging API at the recovery database.
4. Run `/health/ready`.
5. Smoke test auth, league read, draft room read, roster read, and standings read.

## Required Alerts

- API readiness failure.
- Worker heartbeat stale.
- Draft timeout runner failures.
- Scoring job failure.
- Provider sync stale or failed.
- Database connection saturation.
- Error spike from frontend or backend.
