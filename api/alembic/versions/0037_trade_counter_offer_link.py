"""link replacement counter offers to their original offer

Revision ID: 0037_trade_counter_link
Revises: 0036_worker_health
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0037_trade_counter_link"
down_revision: str | Sequence[str] | None = "0036_worker_health"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "trade_offers",
        sa.Column("countered_from_trade_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_trade_offers_countered_from_trade_id",
        "trade_offers",
        "trade_offers",
        ["countered_from_trade_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_trade_offers_countered_from_trade_id",
        "trade_offers",
        ["countered_from_trade_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_trade_offers_countered_from_trade_id", table_name="trade_offers")
    op.drop_constraint("fk_trade_offers_countered_from_trade_id", "trade_offers", type_="foreignkey")
    op.drop_column("trade_offers", "countered_from_trade_id")
