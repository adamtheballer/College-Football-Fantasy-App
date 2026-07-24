"""Persist canonical roster slot indexes for assignment overlays.

Revision ID: 0053_roster_slot_identity
Revises: 0052_team_schedule_game_logs
"""

from alembic import op
import sqlalchemy as sa


revision = "0053_roster_slot_identity"
down_revision = "0052_team_schedule_game_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("roster_entries", sa.Column("slot_index", sa.Integer(), nullable=True))
    op.execute(
        """
        WITH numbered_entries AS (
            SELECT id, ROW_NUMBER() OVER (
                PARTITION BY team_id, slot
                ORDER BY id
            ) AS row_number
            FROM roster_entries
        )
        UPDATE roster_entries
        SET slot_index = numbered_entries.row_number
        FROM numbered_entries
        WHERE roster_entries.id = numbered_entries.id
        """
    )
    op.alter_column("roster_entries", "slot_index", nullable=False)
    op.create_check_constraint("ck_roster_slot_index_positive", "roster_entries", "slot_index > 0")
    op.create_unique_constraint(
        "uq_roster_team_slot_index",
        "roster_entries",
        ["team_id", "slot", "slot_index"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_roster_team_slot_index", "roster_entries", type_="unique")
    op.drop_constraint("ck_roster_slot_index_positive", "roster_entries", type_="check")
    op.drop_column("roster_entries", "slot_index")
