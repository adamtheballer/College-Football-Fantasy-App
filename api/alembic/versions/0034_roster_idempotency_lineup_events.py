"""roster idempotency and lineup events

Revision ID: 0034_roster_idempotency_lineup_events
Revises: 0033_league_settings_versions_invite_controls
Create Date: 2026-07-06
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0034_roster_idempotency_lineup_events"
down_revision = "0033_league_settings_versions_invite_controls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lineup_change_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("from_slot", sa.String(length=50), nullable=False),
        sa.Column("to_slot", sa.String(length=50), nullable=False),
        sa.Column("lock_state", sa.String(length=50), nullable=False),
        sa.Column("changed_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["changed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lineup_change_events_team_week", "lineup_change_events", ["team_id", "week"])
    op.create_index("ix_lineup_change_events_player_id", "lineup_change_events", ["player_id"])

    with op.batch_alter_table("transactions") as batch_op:
        batch_op.add_column(sa.Column("idempotency_key", sa.String(length=120), nullable=True))
        batch_op.create_index("ix_transactions_idempotency_key", ["idempotency_key"])
        batch_op.create_unique_constraint(
            "uq_transactions_team_idempotency_key",
            ["team_id", "idempotency_key"],
        )


def downgrade() -> None:
    with op.batch_alter_table("transactions") as batch_op:
        batch_op.drop_constraint("uq_transactions_team_idempotency_key", type_="unique")
        batch_op.drop_index("ix_transactions_idempotency_key")
        batch_op.drop_column("idempotency_key")

    op.drop_index("ix_lineup_change_events_player_id", table_name="lineup_change_events")
    op.drop_index("ix_lineup_change_events_team_week", table_name="lineup_change_events")
    op.drop_table("lineup_change_events")
