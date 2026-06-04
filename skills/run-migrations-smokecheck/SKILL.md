---
name: run-migrations-smokecheck
description: Run a local migration smokecheck against the Postgres database used by this repo. Use when validating schema changes or confirming a clean setup.
---

# Run Migrations Smokecheck

## Steps

1. Ensure `.env` is configured with `DATABASE_URL` and start Postgres:
   - `docker-compose up -d db`
2. Apply migrations:
   - `uv run alembic -c api/alembic.ini upgrade head`
3. If troubleshooting, inspect Alembic output and confirm the `alembic_version` table exists.

## Optional validation

- Start the API and hit `/health` to confirm the app can connect to the DB.
- Run `uv run pytest tests/api/test_health.py` for a quick sanity check.
