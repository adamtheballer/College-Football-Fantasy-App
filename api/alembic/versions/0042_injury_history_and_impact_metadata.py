"""injury history and impact metadata

Revision ID: 0042_injury_history_and_impact_metadata
Revises: 0041_projection_metadata
Create Date: 2026-07-07
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0042_injury_history_and_impact_metadata"
down_revision = "0041_projection_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("injuries") as batch_op:
        batch_op.add_column(sa.Column("normalized_status", sa.String(length=20), nullable=False, server_default="healthy"))
        batch_op.add_column(sa.Column("body_part", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("source", sa.String(length=40), nullable=False, server_default="unknown"))
        batch_op.add_column(sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("cleared_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index("ix_injuries_source_updated_at", ["source_updated_at"])

    with op.batch_alter_table("injury_impacts") as batch_op:
        batch_op.add_column(sa.Column("multiplier", sa.Float(), nullable=False, server_default="1.0"))
        batch_op.add_column(sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"))

    op.create_table(
        "injury_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="unknown"),
        sa.Column("normalized_status", sa.String(length=20), nullable=False, server_default="unknown"),
        sa.Column("injury", sa.String(length=200), nullable=True),
        sa.Column("body_part", sa.String(length=100), nullable=True),
        sa.Column("return_timeline", sa.String(length=100), nullable=True),
        sa.Column("practice_level", sa.String(length=20), nullable=True),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("source", sa.String(length=40), nullable=False, server_default="unknown"),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "player_id",
            "season",
            "week",
            "status",
            "injury",
            "source",
            name="uq_injury_history_player_week_state_source",
        ),
    )
    op.create_index("ix_injury_history_player_id", "injury_history", ["player_id"])
    op.create_index("ix_injury_history_season_week", "injury_history", ["season", "week"])
    op.create_index("ix_injury_history_source_updated_at", "injury_history", ["source_updated_at"])


def downgrade() -> None:
    op.drop_index("ix_injury_history_source_updated_at", table_name="injury_history")
    op.drop_index("ix_injury_history_season_week", table_name="injury_history")
    op.drop_index("ix_injury_history_player_id", table_name="injury_history")
    op.drop_table("injury_history")

    with op.batch_alter_table("injury_impacts") as batch_op:
        batch_op.drop_column("confidence")
        batch_op.drop_column("multiplier")

    with op.batch_alter_table("injuries") as batch_op:
        batch_op.drop_index("ix_injuries_source_updated_at")
        batch_op.drop_column("cleared_at")
        batch_op.drop_column("last_seen_at")
        batch_op.drop_column("first_seen_at")
        batch_op.drop_column("source_updated_at")
        batch_op.drop_column("source")
        batch_op.drop_column("body_part")
        batch_op.drop_column("normalized_status")
