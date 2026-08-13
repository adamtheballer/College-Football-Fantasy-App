"""Add durable career events and league rivalry selections.

Revision ID: 0091_career_profile_rivalries
Revises: 0090_expand_league_icon_url
Create Date: 2026-08-13
"""

from alembic import op
import sqlalchemy as sa


revision = "0091_career_profile_rivalries"
down_revision = "0090_expand_league_icon_url"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_career_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("source_key", sa.String(length=240), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("league_id", sa.Integer(), sa.ForeignKey("leagues.id", ondelete="SET NULL"), nullable=True),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="SET NULL"), nullable=True),
        sa.Column("matchup_id", sa.Integer(), sa.ForeignKey("matchups.id", ondelete="SET NULL"), nullable=True),
        sa.Column("trade_id", sa.Integer(), sa.ForeignKey("trade_offers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("draft_id", sa.Integer(), sa.ForeignKey("drafts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("season", sa.Integer(), nullable=True),
        sa.Column("week", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("source_key", name="uq_user_career_events_source_key"),
    )
    op.create_index("ix_user_career_events_user_occurred", "user_career_events", ["user_id", "occurred_at"])
    op.create_index("ix_user_career_events_league", "user_career_events", ["league_id", "season"])
    op.create_table(
        "league_rivalries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("league_id", sa.Integer(), sa.ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rival_team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("selected_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("selected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("rivalry_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("league_id", "season", "team_id", name="uq_league_rivalries_team_season"),
        sa.CheckConstraint("team_id <> rival_team_id", name="ck_league_rivalries_distinct_teams"),
    )
    op.create_index("ix_league_rivalries_league_season", "league_rivalries", ["league_id", "season"])
    op.create_index("ix_league_rivalries_rival_team", "league_rivalries", ["rival_team_id"])


def downgrade() -> None:
    op.drop_index("ix_league_rivalries_rival_team", table_name="league_rivalries")
    op.drop_index("ix_league_rivalries_league_season", table_name="league_rivalries")
    op.drop_table("league_rivalries")
    op.drop_index("ix_user_career_events_league", table_name="user_career_events")
    op.drop_index("ix_user_career_events_user_occurred", table_name="user_career_events")
    op.drop_table("user_career_events")
