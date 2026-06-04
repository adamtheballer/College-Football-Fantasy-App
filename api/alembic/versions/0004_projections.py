"""projection engine tables

Revision ID: 0004_projections
Revises: 0003_scoring_pipeline
Create Date: 2026-03-06 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "0004_projections"
down_revision = "0003_scoring_pipeline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "games",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("external_id", sa.String(length=64), nullable=True),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("season_type", sa.String(length=20), nullable=False, server_default="regular"),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("home_team", sa.String(length=200), nullable=False),
        sa.Column("away_team", sa.String(length=200), nullable=False),
        sa.Column("home_points", sa.Integer(), nullable=True),
        sa.Column("away_points", sa.Integer(), nullable=True),
        sa.Column("neutral_site", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_games_season_week", "games", ["season", "week"])
    op.create_index("ix_games_external_id", "games", ["external_id"])

    op.create_table(
        "game_odds",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("game_id", sa.Integer(), sa.ForeignKey("games.id", ondelete="CASCADE"), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="oddsapi"),
        sa.Column("spread", sa.Float(), nullable=True),
        sa.Column("over_under", sa.Float(), nullable=True),
        sa.Column("home_implied", sa.Float(), nullable=True),
        sa.Column("away_implied", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_game_odds_game_id", "game_odds", ["game_id"])
    op.create_index("ix_game_odds_season_week", "game_odds", ["season", "week"])

    op.create_table(
        "team_game_stats",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("team_name", sa.String(length=200), nullable=False),
        sa.Column("game_id", sa.Integer(), sa.ForeignKey("games.id", ondelete="CASCADE"), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="cfbd"),
        sa.Column("stats", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("team_name", "game_id", name="uq_team_game_stats_team_game"),
    )
    op.create_index("ix_team_game_stats_team_name", "team_game_stats", ["team_name"])
    op.create_index("ix_team_game_stats_season_week", "team_game_stats", ["season", "week"])

    op.create_table(
        "player_game_stats",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("game_id", sa.Integer(), sa.ForeignKey("games.id", ondelete="CASCADE"), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="sportsdata"),
        sa.Column("stats", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("player_id", "game_id", name="uq_player_game_stats_player_game"),
    )
    op.create_index("ix_player_game_stats_player_id", "player_game_stats", ["player_id"])
    op.create_index("ix_player_game_stats_season_week", "player_game_stats", ["season", "week"])

    op.create_table(
        "team_environment",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("team_name", sa.String(length=200), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("expected_plays", sa.Float(), nullable=False, server_default="0"),
        sa.Column("expected_points", sa.Float(), nullable=False, server_default="0"),
        sa.Column("pass_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("rush_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("red_zone_trips", sa.Float(), nullable=False, server_default="0"),
        sa.Column("red_zone_td_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("pace_seconds_per_play", sa.Float(), nullable=False, server_default="0"),
        sa.Column("implied_team_total", sa.Float(), nullable=True),
        sa.Column("spread", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_team_environment_team_name", "team_environment", ["team_name"])
    op.create_index("ix_team_environment_season_week", "team_environment", ["season", "week"])

    op.create_table(
        "defense_ratings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("team_name", sa.String(length=200), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("pass_def_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("rush_def_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("pass_def_tier", sa.String(length=10), nullable=False, server_default="Average"),
        sa.Column("rush_def_tier", sa.String(length=10), nullable=False, server_default="Average"),
        sa.Column("pass_yards_multiplier", sa.Float(), nullable=False, server_default="1"),
        sa.Column("pass_catch_multiplier", sa.Float(), nullable=False, server_default="1"),
        sa.Column("pass_td_multiplier", sa.Float(), nullable=False, server_default="1"),
        sa.Column("pass_turnover_multiplier", sa.Float(), nullable=False, server_default="1"),
        sa.Column("rush_yards_multiplier", sa.Float(), nullable=False, server_default="1"),
        sa.Column("rush_success_multiplier", sa.Float(), nullable=False, server_default="1"),
        sa.Column("rush_td_multiplier", sa.Float(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_defense_ratings_team_name", "defense_ratings", ["team_name"])
    op.create_index("ix_defense_ratings_season_week", "defense_ratings", ["season", "week"])

    op.create_table(
        "usage_shares",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("rush_share", sa.Float(), nullable=False, server_default="0"),
        sa.Column("target_share", sa.Float(), nullable=False, server_default="0"),
        sa.Column("red_zone_share", sa.Float(), nullable=False, server_default="0"),
        sa.Column("inside_five_share", sa.Float(), nullable=False, server_default="0"),
        sa.Column("snap_share", sa.Float(), nullable=False, server_default="0"),
        sa.Column("route_share", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_usage_shares_player_id", "usage_shares", ["player_id"])
    op.create_index("ix_usage_shares_season_week", "usage_shares", ["season", "week"])

    op.create_table(
        "injuries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="FULL"),
        sa.Column("practice_level", sa.String(length=20), nullable=True),
        sa.Column("is_game_time_decision", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_returning", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_injuries_player_id", "injuries", ["player_id"])
    op.create_index("ix_injuries_season_week", "injuries", ["season", "week"])

    op.create_table(
        "preseason_priors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("priors", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("player_id", "season", name="uq_preseason_priors_player_season"),
    )
    op.create_index("ix_preseason_priors_player_id", "preseason_priors", ["player_id"])

    op.create_table(
        "weekly_projections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("pass_attempts", sa.Float(), nullable=False, server_default="0"),
        sa.Column("rush_attempts", sa.Float(), nullable=False, server_default="0"),
        sa.Column("targets", sa.Float(), nullable=False, server_default="0"),
        sa.Column("receptions", sa.Float(), nullable=False, server_default="0"),
        sa.Column("expected_plays", sa.Float(), nullable=False, server_default="0"),
        sa.Column("expected_rush_per_play", sa.Float(), nullable=False, server_default="0"),
        sa.Column("expected_td_per_play", sa.Float(), nullable=False, server_default="0"),
        sa.Column("pass_yards", sa.Float(), nullable=False, server_default="0"),
        sa.Column("rush_yards", sa.Float(), nullable=False, server_default="0"),
        sa.Column("rec_yards", sa.Float(), nullable=False, server_default="0"),
        sa.Column("pass_tds", sa.Float(), nullable=False, server_default="0"),
        sa.Column("rush_tds", sa.Float(), nullable=False, server_default="0"),
        sa.Column("rec_tds", sa.Float(), nullable=False, server_default="0"),
        sa.Column("interceptions", sa.Float(), nullable=False, server_default="0"),
        sa.Column("fantasy_points", sa.Float(), nullable=False, server_default="0"),
        sa.Column("floor", sa.Float(), nullable=False, server_default="0"),
        sa.Column("ceiling", sa.Float(), nullable=False, server_default="0"),
        sa.Column("boom_prob", sa.Float(), nullable=False, server_default="0"),
        sa.Column("bust_prob", sa.Float(), nullable=False, server_default="0"),
        sa.Column("qb_rating", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("player_id", "season", "week", name="uq_weekly_projections_player_season_week"),
    )
    op.create_index("ix_weekly_projections_player_id", "weekly_projections", ["player_id"])
    op.create_index("ix_weekly_projections_season_week", "weekly_projections", ["season", "week"])

    op.create_table(
        "projection_inputs_audit",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("model_version", sa.String(length=50), nullable=False, server_default="v1"),
        sa.Column("inputs", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("player_id", "season", "week", name="uq_projection_inputs_player_season_week"),
    )
    op.create_index("ix_projection_inputs_player_id", "projection_inputs_audit", ["player_id"])
    op.create_index("ix_projection_inputs_season_week", "projection_inputs_audit", ["season", "week"])


def downgrade() -> None:
    op.drop_index("ix_projection_inputs_season_week", table_name="projection_inputs_audit")
    op.drop_index("ix_projection_inputs_player_id", table_name="projection_inputs_audit")
    op.drop_table("projection_inputs_audit")

    op.drop_index("ix_weekly_projections_season_week", table_name="weekly_projections")
    op.drop_index("ix_weekly_projections_player_id", table_name="weekly_projections")
    op.drop_table("weekly_projections")

    op.drop_index("ix_preseason_priors_player_id", table_name="preseason_priors")
    op.drop_table("preseason_priors")

    op.drop_index("ix_injuries_season_week", table_name="injuries")
    op.drop_index("ix_injuries_player_id", table_name="injuries")
    op.drop_table("injuries")

    op.drop_index("ix_usage_shares_season_week", table_name="usage_shares")
    op.drop_index("ix_usage_shares_player_id", table_name="usage_shares")
    op.drop_table("usage_shares")

    op.drop_index("ix_defense_ratings_season_week", table_name="defense_ratings")
    op.drop_index("ix_defense_ratings_team_name", table_name="defense_ratings")
    op.drop_table("defense_ratings")

    op.drop_index("ix_team_environment_season_week", table_name="team_environment")
    op.drop_index("ix_team_environment_team_name", table_name="team_environment")
    op.drop_table("team_environment")

    op.drop_index("ix_player_game_stats_season_week", table_name="player_game_stats")
    op.drop_index("ix_player_game_stats_player_id", table_name="player_game_stats")
    op.drop_table("player_game_stats")

    op.drop_index("ix_team_game_stats_season_week", table_name="team_game_stats")
    op.drop_index("ix_team_game_stats_team_name", table_name="team_game_stats")
    op.drop_table("team_game_stats")

    op.drop_index("ix_game_odds_season_week", table_name="game_odds")
    op.drop_index("ix_game_odds_game_id", table_name="game_odds")
    op.drop_table("game_odds")

    op.drop_index("ix_games_external_id", table_name="games")
    op.drop_index("ix_games_season_week", table_name="games")
    op.drop_table("games")
