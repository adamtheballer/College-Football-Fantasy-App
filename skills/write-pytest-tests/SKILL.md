---
name: write-pytest-tests
description: Add or update pytest tests for the FastAPI backend in this repo. Use when covering new endpoints, schema changes, or bug fixes.
---

# Write Pytest Tests

## Structure

- Place API tests in `tests/api`.
- Use the `client` fixture from `tests/conftest.py` for FastAPI `TestClient` access.
- The fixture uses a local sqlite database; keep tests isolated and stateless.

## Patterns to follow

- Arrange data through API calls rather than direct DB writes when possible.
- Assert status codes, response shapes, and key fields.
- For list endpoints, assert `{data, total, limit, offset}`.

## When adding models

- If a new model module is introduced, import it in `tests/conftest.py` so `Base.metadata` includes it.

## Run tests

- `uv run pytest` or `uv run pytest tests/api/test_<feature>.py`
