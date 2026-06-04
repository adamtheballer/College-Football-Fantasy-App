"""add league week state and trade offer lifecycle tables

Revision ID: 0021_week_state_trade_lifecycle
Revises: 0020_draft_realtime_foundation
Create Date: 2026-05-26 00:00:02.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0021_week_state_trade_lifecycle"
down_revision: str | None = "0020_draft_realtime_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "league_week_states",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="open"),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("corrected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("league_id", "season", "week", name="uq_league_week_states_league_season_week"),
    )
    op.create_index("ix_league_week_states_league_id", "league_week_states", ["league_id"], unique=False)
    op.create_index("ix_league_week_states_season_week", "league_week_states", ["season", "week"], unique=False)
    op.create_index("ix_league_week_states_status", "league_week_states", ["status"], unique=False)

    op.create_table(
        "trade_offers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("proposal_ref", sa.String(length=32), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("from_team_id", sa.Integer(), nullable=False),
        sa.Column("to_team_id", sa.Integer(), nullable=False),
        sa.Column("from_user_id", sa.Integer(), nullable=False),
        sa.Column("to_user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="open"),
        sa.Column("review_status", sa.String(length=30), nullable=False, server_default="none"),
        sa.Column("review_mode", sa.String(length=30), nullable=False, server_default="commissioner"),
        sa.Column("note", sa.String(length=300), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["from_team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["to_team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["from_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["to_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("proposal_ref", name="uq_trade_offers_proposal_ref"),
    )
    op.create_index("ix_trade_offers_league_id", "trade_offers", ["league_id"], unique=False)
    op.create_index("ix_trade_offers_status", "trade_offers", ["status"], unique=False)
    op.create_index("ix_trade_offers_from_team_id", "trade_offers", ["from_team_id"], unique=False)
    op.create_index("ix_trade_offers_to_team_id", "trade_offers", ["to_team_id"], unique=False)
    op.create_index("ix_trade_offers_expires_at", "trade_offers", ["expires_at"], unique=False)

    op.create_table(
        "trade_offer_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("trade_offer_id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("side", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["trade_offer_id"], ["trade_offers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trade_offer_items_trade_offer_id", "trade_offer_items", ["trade_offer_id"], unique=False)
    op.create_index("ix_trade_offer_items_player_id", "trade_offer_items", ["player_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_trade_offer_items_player_id", table_name="trade_offer_items")
    op.drop_index("ix_trade_offer_items_trade_offer_id", table_name="trade_offer_items")
    op.drop_table("trade_offer_items")

    op.drop_index("ix_trade_offers_expires_at", table_name="trade_offers")
    op.drop_index("ix_trade_offers_to_team_id", table_name="trade_offers")
    op.drop_index("ix_trade_offers_from_team_id", table_name="trade_offers")
    op.drop_index("ix_trade_offers_status", table_name="trade_offers")
    op.drop_index("ix_trade_offers_league_id", table_name="trade_offers")
    op.drop_table("trade_offers")

    op.drop_index("ix_league_week_states_status", table_name="league_week_states")
    op.drop_index("ix_league_week_states_season_week", table_name="league_week_states")
    op.drop_index("ix_league_week_states_league_id", table_name="league_week_states")
    op.drop_table("league_week_states")
