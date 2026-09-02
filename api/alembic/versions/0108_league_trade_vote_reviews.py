"""Make league trade voting the sole trade-review rule.

Revision ID: 0108_league_trade_vote
Revises: 0107_account_delete
"""

import sqlalchemy as sa
from alembic import op


revision = "0108_league_trade_vote"
down_revision = "0107_account_delete"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Runtime code normalizes legacy settings to the mandatory league-vote
    # process.  Keep this schema migration forward-only: it must not rewrite
    # live league configuration or pending transactions.
    op.create_index(
        "uq_trade_reviews_vote_by_member",
        "trade_reviews",
        ["trade_offer_id", "reviewer_user_id"],
        unique=True,
        postgresql_where=sa.text("action IN ('uphold', 'veto')"),
        sqlite_where=sa.text("action IN ('uphold', 'veto')"),
    )


def downgrade() -> None:
    op.drop_index("uq_trade_reviews_vote_by_member", table_name="trade_reviews")
    # Keep live settings intact rather than rewriting a completed review.
