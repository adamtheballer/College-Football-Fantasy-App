# Beta 2026 Release-Candidate Validation

Release branch: `release/beta-2026-runtime`
Candidate commit: record the final `HEAD` immediately before the merge
Validation date: 2026-07-26

## Verified in the candidate

| Gate | Evidence | Result |
| --- | --- | --- |
| Web production build | `cd web && npm run build` | Passed |
| Frontend typecheck and unit tests | `cd web && npm run typecheck && npm test` | Passed: 129 tests |
| Full backend suite | `PYTHONPATH=. uv run pytest -q tests --disable-warnings` | Passed; no cached failures remained |
| Critical workflow suite | `tests/api/test_waiver_processing.py`, `test_roster_workflows.py`, `test_leagues.py`, and `test_trades.py` | Passed: 77 tests |
| Waiver lifecycle | Regression coverage verifies bid phase, post-clear instant adds, per-player kickoff locks, and the next-week return to bid phase | Passed |
| Lifecycle concurrency | Four concurrent workers against a clean PostgreSQL database; verifies one draft auto-pick, one waiver award/FAAB charge, isolated trade outcomes, and scoring rollback | Passed |
| Migration graph | `alembic heads` | One head: `0076_saturday_pick_6` |
| Upgrade path | Isolated empty PostgreSQL database upgraded through `0075_processed_waiver_claims` and then `head` | Passed |
| Migration drift | `alembic check` against the beta database | Passed: no new upgrade operations |
| Database readiness | `scripts/check_alembic_head.py` against the beta database | Passed at `0076_saturday_pick_6` |
| Real-stack browser gate | Isolated Docker stack: signup, session persistence, draft-pool load, two-manager draft synchronization, countdown, and auto-picks | Passed: 2 Playwright tests |
| Production configuration contract | Runtime validator and deployment manifest require HTTPS UI origin, secure cookies, SMTP/TLS, legal/support URLs, and SportsData scoring credentials | Passed: 19 tests |
| League route data integrity | Removed the hard-coded demo league and its roster, matchup, waiver, settings, and watchlist responses; supported league routes now require real API data and show retryable errors instead of fictional league state | Passed: typecheck, 129 frontend tests, production build |

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
