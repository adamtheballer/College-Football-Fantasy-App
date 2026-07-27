"""add league player event ledger

Revision ID: 0078_league_player_events
Revises: 0077_correct_desean_bishop_class
"""

from alembic import op
import sqlalchemy as sa


revision = "0078_league_player_events"
down_revision = "0077_correct_desean_bishop_class"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "league_player_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("league_id", sa.Integer(), sa.ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("event_key", sa.String(length=200), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fantasy_team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="SET NULL")),
        sa.Column("from_fantasy_team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="SET NULL")),
        sa.Column("to_fantasy_team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="SET NULL")),
        sa.Column("manager_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("draft_id", sa.Integer(), sa.ForeignKey("drafts.id", ondelete="SET NULL")),
        sa.Column("draft_pick_id", sa.Integer(), sa.ForeignKey("draft_picks.id", ondelete="SET NULL")),
        sa.Column("trade_id", sa.Integer(), sa.ForeignKey("trade_offers.id", ondelete="SET NULL")),
        sa.Column("waiver_claim_id", sa.Integer(), sa.ForeignKey("waiver_claims.id", ondelete="SET NULL")),
        sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("transactions.id", ondelete="SET NULL")),
        sa.Column("player_name_snapshot", sa.String(length=200), nullable=False),
        sa.Column("position_snapshot", sa.String(length=20), nullable=False),
        sa.Column("school_snapshot", sa.String(length=200), nullable=False),
        sa.Column("player_value_snapshot", sa.Float()),
        sa.Column("fantasy_team_name_snapshot", sa.String(length=200)),
        sa.Column("from_team_name_snapshot", sa.String(length=200)),
        sa.Column("to_team_name_snapshot", sa.String(length=200)),
        sa.Column("manager_name_snapshot", sa.String(length=200)),
        sa.Column("event_metadata_json", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("league_id", "event_key", name="uq_league_player_events_event_key"),
    )
    op.create_index("ix_league_player_events_league_player_occurred", "league_player_events", ["league_id", "player_id", "occurred_at"])
    op.create_index("ix_league_player_events_league_occurred", "league_player_events", ["league_id", "occurred_at"])
    op.create_index("ix_league_player_events_player_id", "league_player_events", ["player_id"])


def downgrade() -> None:
    op.drop_table("league_player_events")
