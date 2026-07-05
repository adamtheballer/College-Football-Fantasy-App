"""add optional unique usernames to users

Revision ID: 0019_usernames
Revises: 0018_sheet_projection_fields
Create Date: 2026-07-01 20:40:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0019_usernames"
down_revision: str | None = "0018_sheet_projection_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _existing_columns() -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns("users")}


def _existing_indexes() -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {index["name"] for index in inspector.get_indexes("users")}


def upgrade() -> None:
    if "username" not in _existing_columns():
        op.add_column("users", sa.Column("username", sa.String(length=80), nullable=True))
    if "ix_users_username" not in _existing_indexes():
        op.create_index("ix_users_username", "users", ["username"], unique=True)


def downgrade() -> None:
    if "ix_users_username" in _existing_indexes():
        op.drop_index("ix_users_username", table_name="users")
    if "username" in _existing_columns():
        op.drop_column("users", "username")
