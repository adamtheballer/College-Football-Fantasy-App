"""watchlist metadata and alerts

Revision ID: 0043_watchlist_metadata_alerts
Revises: 0042_injury_history_and_impact_metadata
Create Date: 2026-07-07
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0043_watchlist_metadata_alerts"
down_revision = "0042_injury_history_and_impact_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("watchlist_players") as batch_op:
        batch_op.add_column(sa.Column("team_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("notes", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("priority", sa.Integer(), nullable=False, server_default="3"))
        batch_op.add_column(sa.Column("tags", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("alert_available", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch_op.add_column(sa.Column("alert_injury", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch_op.add_column(sa.Column("alert_projection", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch_op.add_column(sa.Column("alert_ownership", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch_op.add_column(sa.Column("alert_matchup", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch_op.create_foreign_key(
            "fk_watchlist_players_team_id_teams",
            "teams",
            ["team_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_watchlist_players_team_id", ["team_id"])
        batch_op.create_index("ix_watchlist_players_priority", ["priority"])


def downgrade() -> None:
    with op.batch_alter_table("watchlist_players") as batch_op:
        batch_op.drop_index("ix_watchlist_players_priority")
        batch_op.drop_index("ix_watchlist_players_team_id")
        batch_op.drop_constraint("fk_watchlist_players_team_id_teams", type_="foreignkey")
        batch_op.drop_column("alert_matchup")
        batch_op.drop_column("alert_ownership")
        batch_op.drop_column("alert_projection")
        batch_op.drop_column("alert_injury")
        batch_op.drop_column("alert_available")
        batch_op.drop_column("tags")
        batch_op.drop_column("priority")
        batch_op.drop_column("notes")
        batch_op.drop_column("team_id")
