# Beta 2026 Release-Candidate Validation

Release branch: `release/beta-2026`
Candidate commit: the commit containing this validation record (record the exact SHA in the final PR and release tag)
Validation date: 2026-07-27

## Verified in the candidate

| Gate | Evidence | Result |
| --- | --- | --- |
| Web production build | `cd web && npm run build` | Passed |
| Frontend typecheck and unit tests | `npm --prefix web run typecheck && npm --prefix web test` | Passed: 26 files, 137 tests |
| Full backend suite | `PYTHONPATH=. uv run pytest -q tests --disable-warnings` | Passed: 341 tests, 6 non-blocking warnings |
| Waiver lifecycle | Regression coverage verifies bid phase, post-clear instant adds, per-player kickoff locks, and the next-week return to bid phase | Passed |
| Lifecycle concurrency | Four concurrent workers against a clean PostgreSQL database; verifies one draft auto-pick, one waiver award/FAAB charge, isolated trade outcomes, and scoring rollback | Passed: `draft_auto_picked=1`, `waiver_processed=1`, `faab_spent=7`, expected accept/cancel and worker/veto outcomes, and rollback verified |
| Migration graph | `alembic heads` | One head: `0082_release_audit_timestamps` |
| Upgrade path | Isolated empty PostgreSQL database upgraded to `head`; the subsequent Alembic drift check passed | Passed; temporary database removed after verification |
| Existing beta upgrade | `alembic upgrade head` from the prior runtime revision | Passed to `0082_release_audit_timestamps` |
| Migration drift | `alembic check` against the beta database | Passed: no new upgrade operations |
| Database readiness | `scripts/check_alembic_head.py` and `GET /health/ready` against the rebuilt local stack | Passed at `0082_release_audit_timestamps` |
| Model registry parity | Legacy standalone registry entrypoint and canonical FastAPI/Alembic registry import the same model set | Passed: 2 focused tests; standalone `Player` query succeeds |
| Real-stack browser gate | Isolated Docker stack: signup, session persistence, draft-pool load, two-manager draft synchronization, countdown, and auto-picks | Passed: 2 Playwright tests |
| Player-pool integrity | Read-only audit of the canonical draft universe | Passed: 825 eligible players; zero non-approved schools, duplicate identities, and missing season projections |
| Production configuration contract | Runtime validator and deployment manifest require HTTPS UI origin, secure cookies, SMTP/TLS, legal/support URLs, and SportsData scoring credentials | Passed: 19 tests |
| League route data integrity | Removed the hard-coded demo league and its roster, matchup, waiver, settings, and watchlist responses; supported league routes now require real API data and show retryable errors instead of fictional league state | Passed: typecheck, 137 frontend tests, production build |

## Release-reconciliation fixes included in this candidate

- Added `0082_release_audit_timestamps`, which backfills and makes audit timestamps non-nullable. This reconciles migrations `0078` and `0079` with the shared timestamp model and prevents a false Alembic-drift failure.
- Replaced the stale legacy model-registry list with a delegate to the canonical FastAPI/Alembic registry. Standalone imports can no longer silently omit recently added models.
- Updated the lifecycle concurrency fixture to use an approved Power 4 school. The production eligibility guard remains strict; the test now exercises worker locking instead of intentionally-invalid player selection.
- Rebuilt the local API, web, and lifecycle-worker images after the database upgrade. The prior readiness failure was caused by an older API image expecting migration `0081` while the database was already at `0082`; the rebuilt candidate reports ready with matching revisions.

## Waiver timing contract

1. Before the scheduled weekly processing time, eligible unrostered players require waiver claims and bids.
2. After that week has processed, every still-unrostered eligible player is an instant add with no FAAB bid or waiver-priority use.
3. An individual player becomes unavailable at that player's own kickoff.
4. When the next college-football week begins, the league returns to its normal waiver-bid phase until the next scheduled clear.

## Required production gates before merge/deploy

These are operations checks and cannot be proven from a local candidate alone. The deployment owner must record each result before merging this candidate into `main`.

- [ ] Staging deploy uses this exact commit and `/health/ready` returns `200`.
- [ ] Production environment configuration has a non-default JWT secret, HTTPS-only CORS, secure refresh cookies, SMTP, and production scoring-provider credentials.
- [ ] A fresh production-compatible database backup exists.
- [ ] A restore drill has been completed in isolated staging.
- [ ] Scheduled production workers are configured, including the lifecycle worker that processes waiver windows.
- [ ] Monitoring is active for readiness, worker heartbeat, failed scoring runs, and provider import failures.
- [ ] A designated release owner approves the release and tags the exact `main` commit (for example, `beta-v0.1.0`).

See [Production Operations Runbook](../operations/production-operations.md) for the deployment, rollback, backup, and incident procedures.
