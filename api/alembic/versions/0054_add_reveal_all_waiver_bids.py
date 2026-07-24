"""Add the missing waiver bid visibility setting.

Revision ID: 0054_add_reveal_all_waiver_bids
Revises: 0053_roster_slot_identity
"""

from alembic import op
import sqlalchemy as sa


revision = "0054_add_reveal_all_waiver_bids"
down_revision = "0053_roster_slot_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "league_settings",
        sa.Column(
            "reveal_all_waiver_bids",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("league_settings", "reveal_all_waiver_bids")
