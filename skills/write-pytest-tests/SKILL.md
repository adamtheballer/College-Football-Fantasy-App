---
name: write-pytest-tests
description: Add or update behavior-focused pytest coverage for this repo's FastAPI backend, services, database workflows, integrations, and bug fixes. Use when implementing endpoints, state transitions, calculations, schema changes, authorization, or regression tests.
---

# Write Pytest Tests

## Structure

- Place API tests in `tests/api`.
- Use the `client` fixture from `tests/conftest.py` for FastAPI `TestClient` access.
- Keep tests isolated and stateless.
- The default fixture uses SQLite. Do not claim it validates Postgres row locking, constraints, migration state, or concurrency semantics.
- When behavior depends on Postgres, add or run a Postgres-backed test path. If the repo does not yet provide one, report that verification gap explicitly.

## Patterns to follow

- Start from the invariant or user-visible behavior the test protects.
- Arrange data through API calls rather than direct DB writes when possible.
- Use direct database setup when the scenario requires otherwise-impossible legacy, concurrent, or failure state.
- Cover applicable success, validation, unauthenticated, wrong-actor, not-found, and conflict cases.
- Assert exact calculated values and meaningful fields, not only status codes.
- Assert state before and after failed mutations when data integrity matters.
- For workflows with statuses, enumerate allowed transitions and pin rejected transitions.
- Control time by monkeypatching the project clock or helper; do not add sleep-based tests.
- Mock external providers at the integration boundary while preserving normalization and persistence behavior.
- For collection endpoints, assert the exact declared response model; require `{data, total, limit, offset}` only for paginated contracts.

## Database-specific tests

- Use pre/post snapshots for rollback, atomicity, and idempotency assertions.
- Use database constraints as part of the expected behavior when they enforce the invariant.
- Mark or isolate tests that require Postgres row locking, `SKIP LOCKED`, JSON behavior, timezone semantics, or concurrent transactions.
- Do not claim a SQLite test proves Postgres concurrency behavior.
- Add bounded query-count assertions when the change fixes an N+1 or hot-path regression.

## When adding models

- If a new model module is introduced, import it in `tests/conftest.py` so `Base.metadata` includes it.

## Run tests

- Run the smallest affected file first: `PYTHONPATH=. uv run pytest -q tests/api/test_<feature>.py`.
- Run related workflow suites when models or shared services changed.
- Run `PYTHONPATH=. uv run pytest -q tests` before completion when the change is broad or high risk.
- Report any Postgres-only coverage that could not be executed locally.
