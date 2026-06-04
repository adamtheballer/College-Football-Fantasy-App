---
name: author-db-model-change
description: Update SQLAlchemy models for the CollegeFootballFantasy database, including relationships, metadata registration, and downstream schema/CRUD alignment. Use when adding or modifying tables or columns.
---

# Author DB Model Change

## Steps

1. Edit or add SQLAlchemy models in `api/app/models` and prefer `TimestampMixin` for created/updated timestamps.
2. Define columns with `mapped_column(...)` and type annotations for SQLAlchemy 2.0 style.
3. Add relationships with `relationship(..., back_populates=...)` and match the other side of the relation.
4. If you add a new model module, import it in `api/alembic/env.py` so Alembic sees it.
5. Update Pydantic schemas in `api/app/schemas` to reflect the new fields.
6. Update CRUD functions in `api/app/crud` to handle the new fields or relationships.

## Constraints and conventions

- Keep table names plural (e.g., `__tablename__ = "leagues"`).
- Use indexed columns for common filters (see `Player.position` and `Player.school`).
- Keep relationship cascade behavior consistent with existing models (e.g., `cascade="all, delete-orphan"`).

## Follow-up

- Generate and review an Alembic migration after model changes.
- Add or update tests to cover the new data shape.
