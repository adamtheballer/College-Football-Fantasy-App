"""use proposed trade offer status

Revision ID: 0040_trade_offer_proposed_status
Revises: 0039_unique_real_draft_per_league
Create Date: 2026-06-14 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op


revision = "0040_trade_offer_proposed_status"
down_revision = "0039_unique_real_draft_per_league"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE trade_offers SET status = 'proposed' WHERE status = 'open'")
    op.alter_column(
        "trade_offers",
        "status",
        existing_type=sa.String(length=30),
        existing_nullable=False,
        server_default="proposed",
    )


def downgrade() -> None:
    op.execute("UPDATE trade_offers SET status = 'open' WHERE status = 'proposed'")
    op.alter_column(
        "trade_offers",
        "status",
        existing_type=sa.String(length=30),
        existing_nullable=False,
        server_default="open",
    )
