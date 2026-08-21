"""Track official availability-source provenance and event idempotency.

Revision ID: 0100_official_avail
Revises: 0099_permanent_rivalries
"""

import sqlalchemy as sa
from alembic import op


revision = "0100_official_avail"
down_revision = "0099_permanent_rivalries"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("player_availability_events", "player_news_events"):
        op.add_column(table, sa.Column("source_url", sa.String(length=1000), nullable=True))
        op.add_column(table, sa.Column("content_hash", sa.String(length=64), nullable=True))
        op.create_index(f"ix_{table}_content_hash", table, ["content_hash"])


def downgrade() -> None:
    for table in ("player_news_events", "player_availability_events"):
        op.drop_index(f"ix_{table}_content_hash", table_name=table)
        op.drop_column(table, "content_hash")
        op.drop_column(table, "source_url")
