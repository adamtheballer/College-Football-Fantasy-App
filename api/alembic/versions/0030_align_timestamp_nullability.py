"""align timestamp nullability with model metadata

Revision ID: 0030_align_timestamp_nullability
Revises: 0029_player_sheet_adp_index
Create Date: 2026-07-14 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0030_align_timestamp_nullability"
down_revision: str | None = "0029_player_sheet_adp_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _existing_tables() -> set[str]:
    bind = op.get_bind()
    return set(sa.inspect(bind).get_table_names())


def _existing_columns(table_name: str) -> set[str]:
    bind = op.get_bind()
    return {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def _set_timestamp_nullable(nullable: bool) -> None:
    tables = _existing_tables()
    for table_name in sorted(tables - {"alembic_version"}):
        columns = _existing_columns(table_name)
        for column_name in ("created_at", "updated_at"):
            if column_name not in columns:
                continue
            if not nullable:
                op.execute(
                    sa.text(f"UPDATE {sa.sql.quoted_name(table_name, False)} SET {column_name} = now() WHERE {column_name} IS NULL")
                )
            op.alter_column(
                table_name,
                column_name,
                existing_type=sa.DateTime(timezone=True),
                nullable=nullable,
            )


def upgrade() -> None:
    _set_timestamp_nullable(False)


def downgrade() -> None:
    _set_timestamp_nullable(True)
