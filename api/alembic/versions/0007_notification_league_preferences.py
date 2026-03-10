"""notification league preferences

Revision ID: 0007_notif_league_prefs
Revises: 0006_league_flow
Create Date: 2026-03-08 00:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_notif_league_prefs"
down_revision = "0006_league_flow"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_league_preferences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_key", sa.String(length=100), nullable=False),
        sa.Column(
            "league_id",
            sa.Integer(),
            sa.ForeignKey("leagues.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("injury_alerts", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("big_play_alerts", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("projection_alerts", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("user_key", "league_id", name="uq_notification_league_user"),
    )
    op.create_index(
        "ix_notification_league_preferences_user_key",
        "notification_league_preferences",
        ["user_key"],
    )
    op.create_index(
        "ix_notification_league_preferences_league_id",
        "notification_league_preferences",
        ["league_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_notification_league_preferences_league_id",
        table_name="notification_league_preferences",
    )
    op.drop_index(
        "ix_notification_league_preferences_user_key",
        table_name="notification_league_preferences",
    )
    op.drop_table("notification_league_preferences")
