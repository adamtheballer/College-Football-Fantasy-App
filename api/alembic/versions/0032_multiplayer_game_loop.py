"""add lineup and weekly scoring tables

Revision ID: 0032_multiplayer_game_loop
Revises: 0031_mock_draft_mp
Create Date: 2026-06-03 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0032_multiplayer_game_loop"
down_revision: str | None = "0031_mock_draft_mp"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "lineups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="editable"),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("league_id", "team_id", "season", "week", name="uq_lineups_team_season_week"),
    )
    op.create_index("ix_lineups_league_week", "lineups", ["league_id", "season", "week"], unique=False)
    op.create_index("ix_lineups_team_week", "lineups", ["team_id", "season", "week"], unique=False)

    op.create_table(
        "fantasy_player_scores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("points", sa.Float(), nullable=False, server_default="0"),
        sa.Column("breakdown_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="computed"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("league_id", "player_id", "season", "week", name="uq_fantasy_player_scores_player_week"),
    )
    op.create_index(
        "ix_fantasy_player_scores_league_week",
        "fantasy_player_scores",
        ["league_id", "season", "week"],
        unique=False,
    )
    op.create_index(
        "ix_fantasy_player_scores_player_week",
        "fantasy_player_scores",
        ["player_id", "season", "week"],
        unique=False,
    )

    op.create_table(
        "lineup_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("lineup_id", sa.Integer(), nullable=False),
        sa.Column("roster_entry_id", sa.Integer(), nullable=True),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("slot", sa.String(length=50), nullable=False),
        sa.Column("is_starter", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["lineup_id"], ["lineups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["roster_entry_id"], ["roster_entries.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lineup_id", "player_id", name="uq_lineup_entries_lineup_player"),
    )
    op.create_index("ix_lineup_entries_lineup_id", "lineup_entries", ["lineup_id"], unique=False)
    op.create_index("ix_lineup_entries_player_id", "lineup_entries", ["player_id"], unique=False)

    op.create_table(
        "team_weekly_scores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("lineup_id", sa.Integer(), nullable=True),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("starter_points", sa.Float(), nullable=False, server_default="0"),
        sa.Column("bench_points", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_points", sa.Float(), nullable=False, server_default="0"),
        sa.Column("breakdown_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lineup_id"], ["lineups.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("league_id", "team_id", "season", "week", name="uq_team_weekly_scores_team_week"),
    )
    op.create_index("ix_team_weekly_scores_league_week", "team_weekly_scores", ["league_id", "season", "week"], unique=False)
    op.create_index("ix_team_weekly_scores_team_week", "team_weekly_scores", ["team_id", "season", "week"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_team_weekly_scores_team_week", table_name="team_weekly_scores")
    op.drop_index("ix_team_weekly_scores_league_week", table_name="team_weekly_scores")
    op.drop_table("team_weekly_scores")

    op.drop_index("ix_lineup_entries_player_id", table_name="lineup_entries")
    op.drop_index("ix_lineup_entries_lineup_id", table_name="lineup_entries")
    op.drop_table("lineup_entries")

    op.drop_index("ix_fantasy_player_scores_player_week", table_name="fantasy_player_scores")
    op.drop_index("ix_fantasy_player_scores_league_week", table_name="fantasy_player_scores")
    op.drop_table("fantasy_player_scores")

    op.drop_index("ix_lineups_team_week", table_name="lineups")
    op.drop_index("ix_lineups_league_week", table_name="lineups")
    op.drop_table("lineups")
