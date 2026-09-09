# Canonical Schedule-Time Synchronization

`team_schedules.kickoff_at` is the single kickoff-time authority for roster
rows, matchup rows, player cards, lineup locks, notifications, and Saturday
Pick 6. The schedule-time synchronizer reconciles that table with the approved
provider schedule; updating the provider `games` mirror alone is not enough.

## Production configuration

Set these Railway environment variables on the API/lifecycle-worker service:

```text
SCHEDULE_SYNC_ENABLED=true
SCHEDULE_SYNC_SOURCE=auto
SCHEDULE_SYNC_HOUR_ET=7
CURRENT_SEASON_YEAR=2026
```

`auto` uses SportsData when its configured schedule capability is enabled and
falls back to ESPN otherwise. The worker is due-gated and persistent: a
successful run occurs at most once per Eastern-calendar day from Tuesday
through Saturday at or after the configured hour. Failed attempts use a
30-minute backoff, rather than retrying on every lifecycle tick. It retains
unresolved `TBD` rows for retry rather than inventing a time. Disable the capability immediately with
`SCHEDULE_SYNC_ENABLED=false` if a provider issue is suspected.

## Safe operational sequence

1. Deploy the migration and API/lifecycle-worker code together.
2. Inspect the current week without writes:

   ```bash
   PYTHONPATH=. uv run python scripts/sync_schedule_times.py --season 2026 --week 2 --force-current-week
   ```

3. Review returned `issues`. A match must agree on both stored participants;
   duplicate, mismatched, or provider-missing-time rows remain untouched.
4. Apply only after review:

   ```bash
   PYTHONPATH=. uv run python scripts/sync_schedule_times.py --season 2026 --week 2 --force-current-week --apply
   ```

The protected API equivalent is `POST /admin/schedules/sync`. Open exceptions
are available at `GET /admin/schedules/issues`. An administrator can apply a
reviewed correction with `PUT /admin/schedules/{schedule_id}/kickoff`; manual
overrides are never overwritten by provider retries and are recorded in the
identity audit trail.

## Safety guarantees

- All timestamps are normalized to UTC before persistence.
- A provider cannot replace a confirmed/manual kickoff with `TBD`.
- Final games are not automatically rewritten outside an explicit forced run.
- One provider event is accepted only for an exact, unique team/opponent pair.
- API/provider failures are recorded in `provider_sync_states`; the lifecycle
  worker keeps running and retries during the next permitted window.
