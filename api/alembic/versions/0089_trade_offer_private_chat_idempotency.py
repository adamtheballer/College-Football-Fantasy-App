"""Add durable trade-create request idempotency.

Revision ID: 0089_trade_private_chat
Revises: 0088_beta_scoring_lock
Create Date: 2026-08-10
"""

from alembic import op
import sqlalchemy as sa


# PostgreSQL deployments created by this project retain the legacy
# ``alembic_version.version_num VARCHAR(32)`` shape. Keep this identifier
# within that durable database limit so fresh and existing stacks can migrate.
revision = "0089_trade_private_chat"
down_revision = "0088_beta_scoring_lock"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("trade_offers", sa.Column("client_request_id", sa.String(length=100), nullable=True))
    op.create_unique_constraint(
        "uq_trade_offers_creator_client_request",
        "trade_offers",
        ["created_by_user_id", "client_request_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_trade_offers_creator_client_request", "trade_offers", type_="unique")
    op.drop_column("trade_offers", "client_request_id")
