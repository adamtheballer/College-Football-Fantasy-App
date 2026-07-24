"""Persist stable roster slot indexes for canonical roster responses."""

from alembic import op
import sqlalchemy as sa


revision = "0053_roster_slot_identity"
down_revision = "0052_unified_waiver_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("roster_entries", sa.Column("slot_index", sa.Integer(), nullable=True))
    op.execute(
        """
        WITH indexed_entries AS (
            SELECT id, row_number() OVER (
                PARTITION BY team_id, slot
                ORDER BY id
            ) AS slot_index
            FROM roster_entries
        )
        UPDATE roster_entries
        SET slot_index = indexed_entries.slot_index
        FROM indexed_entries
        WHERE roster_entries.id = indexed_entries.id
        """
    )
    op.alter_column("roster_entries", "slot_index", nullable=False)
    op.create_check_constraint(
        "ck_roster_entries_slot_index_positive",
        "roster_entries",
        "slot_index > 0",
    )
    op.create_unique_constraint(
        "uq_roster_team_slot_index",
        "roster_entries",
        ["team_id", "slot", "slot_index"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_roster_team_slot_index", "roster_entries", type_="unique")
    op.drop_constraint("ck_roster_entries_slot_index_positive", "roster_entries", type_="check")
    op.drop_column("roster_entries", "slot_index")
