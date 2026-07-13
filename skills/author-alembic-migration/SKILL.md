---
name: author-alembic-migration
description: Create and review safe Alembic migrations for this repo, including schema changes, constraints, indexes, data backfills, upgrade ordering, and downgrade behavior. Use whenever SQLAlchemy model changes must be represented in the Postgres schema.
---

# Author Alembic Migration

## Steps

1. Inspect `alembic current`, `alembic heads`, recent revisions, and the affected model before generating anything.
2. Confirm new model modules are visible to `api/alembic/env.py` metadata.
3. Generate a migration:
   - `uv run alembic -c api/alembic.ini revision --autogenerate -m "short message"`
4. Follow the repository's sequential revision convention: use the next conflict-free `NNNN_slug` filename and revision ID, and verify `down_revision` names the current head.
5. Review every generated operation. Autogenerate does not understand renames, data intent, safe backfill order, or application compatibility.
6. For a required column on a populated table, sequence the change deliberately: add safely, backfill, verify, then enforce the constraint.
7. Apply the migration to Postgres:
   - `uv run alembic -c api/alembic.ini upgrade head`
8. Run `$run-migrations-smokecheck` and targeted tests.

## Review checklist

- Check column types, nullability, indexes, and constraints.
- Verify rename operations are captured correctly (autogenerate may drop/add instead).
- Check foreign-key delete behavior and uniqueness against existing rows.
- Keep the revision chain linear unless the repository intentionally needs a merge revision.
- Never edit an already-applied migration to represent a new change; add a new revision.
- Make `downgrade()` honest. Reverse the change when safe, or explicitly preserve data that cannot be reconstructed.
- Keep revisions self-contained. Use Alembic operations, SQLAlchemy Core, or revision-local table definitions instead of importing current ORM models, services, or CRUD functions.
- Avoid long table locks and one-transaction backfills when production data volume makes them unsafe.
