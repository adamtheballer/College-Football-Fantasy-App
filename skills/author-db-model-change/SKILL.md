---
name: author-db-model-change
description: Update SQLAlchemy models and database invariants for this repo, including columns, relationships, constraints, indexes, metadata registration, migrations, and downstream contracts. Use when adding or modifying tables, columns, relationships, or persisted state.
---

# Author DB Model Change

## Steps

1. Inspect current queries, serializers, migrations, and existing rows affected by the change.
2. Edit or add SQLAlchemy models in `api/app/models` using SQLAlchemy 2.0 typed mappings and existing timestamp conventions.
3. Encode durable invariants with database constraints where practical: uniqueness, foreign keys, checks, and non-null columns.
4. Add relationships with matching `back_populates` and deliberate cascade and delete behavior.
5. Add indexes for demonstrated filter, ordering, join, or uniqueness requirements; avoid speculative indexes.
6. Import new model modules where Alembic and tests build metadata.
7. Update Pydantic schemas, services or CRUD, frontend types, and fixtures when the persisted shape crosses those boundaries.

## Constraints and conventions

- Keep table names plural (e.g., `__tablename__ = "leagues"`).
- Do not rely only on Python check-then-insert logic for invariants that concurrent transactions can violate.
- Treat nullability tightening and new uniqueness constraints as data migrations: inspect and repair existing rows first.
- Use timezone-aware database columns and project datetime conventions consistently.
- Keep relationship cascade behavior consistent with domain ownership, not merely nearby syntax.

## Follow-up

- Use `$author-alembic-migration` to create and review the matching migration.
- Use `$cross-stack-contract-parity` if the change affects a React-visible contract.
- Add tests for the invariant, failure behavior, deletion behavior, and serialization shape.
- Run `$run-migrations-smokecheck` before calling the change complete.
