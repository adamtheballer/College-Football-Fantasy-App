---
name: author-alembic-migration
description: Create and review Alembic migrations for schema changes in this repo. Use when a model change needs a migration or when adding data backfills.
---

# Author Alembic Migration

## Steps

1. Confirm models are updated and new model modules are imported in `api/alembic/env.py`.
2. Generate a migration:
   - `uv run alembic -c api/alembic.ini revision --autogenerate -m "short message"`
3. Open the new file in `api/alembic/versions` and review the diff for correctness.
4. Edit the migration if you need data moves, defaults, or backfills (`op.execute` or SQLAlchemy expressions).
5. Apply the migration locally:
   - `uv run alembic -c api/alembic.ini upgrade head`

## Review checklist

- Check column types, nullability, indexes, and constraints.
- Verify rename operations are captured correctly (autogenerate may drop/add instead).
- Ensure any data migration is reversible in `downgrade()`.
