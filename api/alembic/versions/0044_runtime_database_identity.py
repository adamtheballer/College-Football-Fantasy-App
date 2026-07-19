"""Add a stable identity for each database instance.

Revision ID: 0044_db_identity
Revises: 0043_merge_chat_integrity
Create Date: 2026-07-17 00:00:00.000000
"""

from collections.abc import Sequence
from datetime import datetime, timezone
from uuid import uuid4

import sqlalchemy as sa
from alembic import op


revision: str = "0044_db_identity"
down_revision: str | None = "0043_merge_chat_integrity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "database_metadata",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("instance_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("instance_id"),
    )
    op.bulk_insert(
        sa.table(
            "database_metadata",
            sa.column("id", sa.Integer()),
            sa.column("instance_id", sa.String()),
            sa.column("created_at", sa.DateTime(timezone=True)),
        ),
        [{"id": 1, "instance_id": str(uuid4()), "created_at": datetime.now(timezone.utc)}],
    )


def downgrade() -> None:
    op.drop_table("database_metadata")
