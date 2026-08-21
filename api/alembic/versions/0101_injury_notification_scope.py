"""Allow injury alerts to cover all or selected leagues.

Revision ID: 0101_injury_notification_scope
Revises: 0100_official_availability_events
"""

import sqlalchemy as sa
from alembic import op


revision = "0101_injury_notification_scope"
down_revision = "0100_official_availability_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "notification_preferences",
        sa.Column(
            "injury_alert_scope",
            sa.String(length=20),
            nullable=False,
            server_default="ALL",
        ),
    )


def downgrade() -> None:
    op.drop_column("notification_preferences", "injury_alert_scope")
