"""Add timestamp-effective windows to weekly availability and news events.

Revision ID: 0066_event_effective_timestamps
Revises: 0065_weekly_projection_pipeline
"""

import sqlalchemy as sa
from alembic import op


revision = "0066_event_effective_timestamps"
down_revision = "0065_weekly_projection_pipeline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("player_availability_events", "player_news_events"):
        op.add_column(table, sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True))
        op.add_column(table, sa.Column("effective_until", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    for table in ("player_news_events", "player_availability_events"):
        op.drop_column(table, "effective_until")
        op.drop_column(table, "effective_from")
