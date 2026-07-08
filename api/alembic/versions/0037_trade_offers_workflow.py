"""trade offers workflow

Revision ID: 0037_trade_offers_workflow
Revises: 0036_mock_draft_queue_export
Create Date: 2026-07-06
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0037_trade_offers_workflow"
down_revision = "0036_mock_draft_queue_export"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trade_offers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("proposing_team_id", sa.Integer(), nullable=False),
        sa.Column("receiving_team_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("message", sa.String(length=500), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["proposing_team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["receiving_team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trade_offers_league_id", "trade_offers", ["league_id"])
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
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["draft_pick_id"], ["draft_picks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["trade_offer_id"], ["trade_offers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trade_offer_items_trade_offer_id", "trade_offer_items", ["trade_offer_id"])
    op.create_index("ix_trade_offer_items_team_id", "trade_offer_items", ["team_id"])
    op.create_index("ix_trade_offer_items_player_id", "trade_offer_items", ["player_id"])

    op.create_table(
        "trade_reviews",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("trade_offer_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["trade_offer_id"], ["trade_offers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trade_reviews_trade_offer_id", "trade_reviews", ["trade_offer_id"])
    op.create_index("ix_trade_reviews_reviewer_user_id", "trade_reviews", ["reviewer_user_id"])


def downgrade() -> None:
    op.drop_index("ix_trade_reviews_reviewer_user_id", table_name="trade_reviews")
    op.drop_index("ix_trade_reviews_trade_offer_id", table_name="trade_reviews")
    op.drop_table("trade_reviews")

    op.drop_index("ix_trade_offer_items_player_id", table_name="trade_offer_items")
    op.drop_index("ix_trade_offer_items_team_id", table_name="trade_offer_items")
    op.drop_index("ix_trade_offer_items_trade_offer_id", table_name="trade_offer_items")
    op.drop_table("trade_offer_items")

    op.drop_index("ix_trade_offers_status", table_name="trade_offers")
    op.drop_index("ix_trade_offers_receiving_team_id", table_name="trade_offers")
    op.drop_index("ix_trade_offers_proposing_team_id", table_name="trade_offers")
    op.drop_index("ix_trade_offers_league_id", table_name="trade_offers")
    op.drop_table("trade_offers")
