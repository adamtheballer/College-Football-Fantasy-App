"""Add trade offer lifecycle tables.

Revision ID: 0023_trade_offer_lifecycle
Revises: 0022_live_scoring_engine
Create Date: 2026-07-10 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0023_trade_offer_lifecycle"
down_revision: str | None = "0022_live_scoring_engine"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "trade_offers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("proposing_team_id", sa.Integer(), nullable=False),
        sa.Column("receiving_team_id", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("message", sa.String(length=1000), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("process_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["proposing_team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["receiving_team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trade_offers_league_id", "trade_offers", ["league_id"])
    op.create_index("ix_trade_offers_process_after", "trade_offers", ["process_after"])
    op.create_index("ix_trade_offers_proposing_team_id", "trade_offers", ["proposing_team_id"])
    op.create_index("ix_trade_offers_receiving_team_id", "trade_offers", ["receiving_team_id"])
    op.create_index("ix_trade_offers_status", "trade_offers", ["status"])

    op.create_table(
        "trade_offer_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("trade_offer_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=True),
        sa.Column("draft_pick_id", sa.Integer(), nullable=True),
        sa.Column("item_type", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["draft_pick_id"], ["draft_picks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["trade_offer_id"], ["trade_offers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trade_offer_items_player_id", "trade_offer_items", ["player_id"])
    op.create_index("ix_trade_offer_items_team_id", "trade_offer_items", ["team_id"])
    op.create_index("ix_trade_offer_items_trade_offer_id", "trade_offer_items", ["trade_offer_id"])

    op.create_table(
        "trade_reviews",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("trade_offer_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("reason", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["trade_offer_id"], ["trade_offers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trade_reviews_action", "trade_reviews", ["action"])
    op.create_index("ix_trade_reviews_reviewer_user_id", "trade_reviews", ["reviewer_user_id"])
    op.create_index("ix_trade_reviews_trade_offer_id", "trade_reviews", ["trade_offer_id"])

    op.create_table(
        "league_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("message_type", sa.String(length=50), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_league_messages_league_id", "league_messages", ["league_id"])
    op.create_index("ix_league_messages_message_type", "league_messages", ["message_type"])


def downgrade() -> None:
    op.drop_index("ix_league_messages_message_type", table_name="league_messages")
    op.drop_index("ix_league_messages_league_id", table_name="league_messages")
    op.drop_table("league_messages")

    op.drop_index("ix_trade_reviews_trade_offer_id", table_name="trade_reviews")
    op.drop_index("ix_trade_reviews_reviewer_user_id", table_name="trade_reviews")
    op.drop_index("ix_trade_reviews_action", table_name="trade_reviews")
    op.drop_table("trade_reviews")

    op.drop_index("ix_trade_offer_items_trade_offer_id", table_name="trade_offer_items")
    op.drop_index("ix_trade_offer_items_team_id", table_name="trade_offer_items")
    op.drop_index("ix_trade_offer_items_player_id", table_name="trade_offer_items")
    op.drop_table("trade_offer_items")

    op.drop_index("ix_trade_offers_status", table_name="trade_offers")
    op.drop_index("ix_trade_offers_receiving_team_id", table_name="trade_offers")
    op.drop_index("ix_trade_offers_proposing_team_id", table_name="trade_offers")
    op.drop_index("ix_trade_offers_process_after", table_name="trade_offers")
    op.drop_index("ix_trade_offers_league_id", table_name="trade_offers")
    op.drop_table("trade_offers")
