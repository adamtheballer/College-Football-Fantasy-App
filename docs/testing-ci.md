# Testing and CI Gates

This project uses a layered test pyramid:

| Layer | Purpose | Primary files |
| --- | --- | --- |
| Unit | Pure domain logic, rule validation, score math | `tests/api/test_scoring_engine.py`, `tests/api/test_scoring_golden_fixtures.py` |
| Service | Transactional DB workflows and idempotency | `tests/api/test_roster_workflows.py`, `tests/api/test_scoring_worker_reliability.py`, `tests/api/test_provider_sync_jobs.py` |
| Route | HTTP behavior, auth, object permissions | `tests/api/test_authorization_matrix.py`, `tests/api/test_leagues.py`, `tests/api/test_trades.py`, `tests/api/test_waiver_processing.py` |
| Integration | Full backend feature flows | `tests/api/test_draft_race_conditions.py`, `tests/api/test_trade_workflow.py`, `tests/api/test_stat_corrections.py` |
| Browser e2e | User-visible app workflows | `web/tests/e2e/auth.spec.ts`, `web/tests/e2e/full-season.spec.ts`, `web/tests/e2e/draft.spec.ts`, `web/tests/e2e/trades-waivers.spec.ts` |

## Required Local Verification

Run the same gates CI runs before merging:

```bash
uv run pytest
uv run alembic -c api/alembic.ini upgrade head
PYTHONPATH=. uv run python scripts/check_alembic_head.py
npm --prefix web ci
npm --prefix web run typecheck
npm --prefix web run test
npm --prefix web run build
npm --prefix web run e2e
```

## CI Gate

`.github/workflows/ci.yml` blocks pull requests on:

- FastAPI import smoke test.
- Alembic migration upgrade.
- Alembic head verification.
- Full backend pytest suite.
- Frontend dependency installation.
- TypeScript typecheck.
- Frontend unit tests.
- Frontend production build.
- Playwright browser e2e tests.

## Race-Prone Coverage

Concurrency and transactional safety are covered by:

- Draft duplicate-pick and integrity-error tests in `tests/api/test_draft_room.py`.
- Draft race coverage contract in `tests/api/test_draft_race_conditions.py`.
- Scoring lock, heartbeat, retry, and stale-provider tests in `tests/api/test_scoring_worker_reliability.py`.
- Roster ownership and lineup lock tests in `tests/api/test_roster_workflows.py`.
- Atomic trade processing tests in `tests/api/test_trades.py`.
- Waiver processing and failure-reason tests in `tests/api/test_waivers.py`.
