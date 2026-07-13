---
name: run-migrations-smokecheck
description: Verify this repo's Alembic migrations against Postgres, including upgrade-to-head, head consistency, model drift, API readiness, and targeted regression tests. Use after authoring migrations, changing models, or validating a deployment database.
---

# Run Migrations Smokecheck

## Steps

1. Confirm the target is a disposable local or explicitly approved environment. Never experiment with downgrade or destructive checks on production.
2. Ensure `.env` is configured with `DATABASE_URL` and start local Postgres when needed:
   - `docker compose up -d db`
3. Inspect migration state:
   - `uv run alembic -c api/alembic.ini current`
   - `uv run alembic -c api/alembic.ini heads`
   - Treat multiple heads as a failure unless the repository intentionally contains branches and the change includes the required merge revision.
4. Apply migrations:
   - `uv run alembic -c api/alembic.ini upgrade head`
5. Verify the database is at the repository head:
   - `PYTHONPATH=. uv run python scripts/check_alembic_head.py`
6. Check for model-versus-migration drift:
   - `uv run alembic -c api/alembic.ini check`
7. Run the import smoke check:
   - `PYTHONPATH=. uv run python -c "from collegefootballfantasy_api.app.main import app; print(app.title)"`
8. When the API is running, require the readiness endpoint to succeed:
   - `curl --fail --silent --show-error http://localhost:8000/health/ready`
9. Run affected tests with `PYTHONPATH=. uv run pytest -q <paths>`.

## Migration-specific validation

- Exercise the upgrade from the revision immediately before a new migration using representative pre-existing rows.
- On a disposable database, run downgrade then upgrade when the downgrade is intended to be supported.
- Verify backfilled values, new constraints, indexes, and foreign-key behavior directly rather than relying only on a successful command exit.
- Report skipped checks and the exact environment used.
