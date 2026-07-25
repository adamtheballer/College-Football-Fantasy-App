"""Persist trade-asset snapshots for resilient historical trade details.

Revision ID: 0069_trade_asset_snapshots
Revises: 0068_google_sheet_history
"""

from alembic import op
import sqlalchemy as sa


revision = "0069_trade_asset_snapshots"
down_revision = "0068_google_sheet_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("trade_offer_items", sa.Column("snapshot_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("trade_offer_items", "snapshot_json")
