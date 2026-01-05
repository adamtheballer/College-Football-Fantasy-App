"""initial schema

Revision ID: 0001_initial
Revises: 
Create Date: 2024-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "leagues",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("platform", sa.String(length=50), nullable=False),
        sa.Column("scoring_type", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_leagues_name", "leagues", ["name"])
    op.create_index("ix_leagues_platform", "leagues", ["platform"])

    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("league_id", sa.Integer(), sa.ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("owner_name", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("league_id", "name", name="uq_team_league_name"),
    )
    op.create_index("ix_teams_league_id", "teams", ["league_id"])

    op.create_table(
        "players",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("external_id", sa.String(length=100), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("position", sa.String(length=10), nullable=False),
        sa.Column("school", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_players_external_id", "players", ["external_id"])
    op.create_index("ix_players_name", "players", ["name"])
    op.create_index("ix_players_position", "players", ["position"])
    op.create_index("ix_players_school", "players", ["school"])

    op.create_table(
        "roster_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slot", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("team_id", "player_id", name="uq_roster_team_player"),
    )
    op.create_index("ix_roster_entries_team_id", "roster_entries", ["team_id"])
    op.create_index("ix_roster_entries_player_id", "roster_entries", ["player_id"])


def downgrade() -> None:
    op.drop_index("ix_roster_entries_player_id", table_name="roster_entries")
    op.drop_index("ix_roster_entries_team_id", table_name="roster_entries")
    op.drop_table("roster_entries")

    op.drop_index("ix_players_school", table_name="players")
    op.drop_index("ix_players_position", table_name="players")
    op.drop_index("ix_players_name", table_name="players")
    op.drop_index("ix_players_external_id", table_name="players")
    op.drop_table("players")

    op.drop_index("ix_teams_league_id", table_name="teams")
    op.drop_table("teams")

    op.drop_index("ix_leagues_platform", table_name="leagues")
    op.drop_index("ix_leagues_name", table_name="leagues")
    op.drop_table("leagues")
