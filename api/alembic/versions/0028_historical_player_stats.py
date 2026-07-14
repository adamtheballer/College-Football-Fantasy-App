"""historical player stats

Revision ID: 0028_historical_player_stats
Revises: 0040_trade_offer_proposed_status
Create Date: 2026-07-12 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0028_historical_player_stats"
down_revision: str | None = "0040_trade_offer_proposed_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "provider_stat_cache",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_player_id", sa.String(length=128), nullable=False),
        sa.Column("request_kind", sa.String(length=80), nullable=False),
        sa.Column("season_start", sa.Integer(), nullable=True),
        sa.Column("season_end", sa.Integer(), nullable=True),
        sa.Column("response_json", sa.JSON(), nullable=False),
        sa.Column("response_hash", sa.String(length=64), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("parser_version", sa.String(length=40), nullable=False),
        sa.Column("schema_version", sa.String(length=40), nullable=False),
        sa.Column("is_valid", sa.Boolean(), nullable=False),
        sa.Column("validation_error", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_player_id", "request_kind", "season_start", "season_end", "response_hash", name="uq_provider_stat_cache_response"),
    )
    op.create_index("ix_provider_stat_cache_lookup", "provider_stat_cache", ["provider", "provider_player_id", "request_kind"])
    op.create_index("ix_provider_stat_cache_expires_at", "provider_stat_cache", ["expires_at"])
    op.create_index("ix_provider_stat_cache_is_valid", "provider_stat_cache", ["is_valid"])

    op.create_table(
        "player_historical_season_stats",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_player_id", sa.String(length=128), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("season_type", sa.String(length=30), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.Column("provider_team_id", sa.String(length=128), nullable=True),
        sa.Column("team_name", sa.String(length=200), nullable=True),
        sa.Column("position", sa.String(length=20), nullable=True),
        sa.Column("games_played", sa.Integer(), nullable=True),
        sa.Column("games_started", sa.Integer(), nullable=True),
        sa.Column("passing_completions", sa.Float(), nullable=True),
        sa.Column("passing_attempts", sa.Float(), nullable=True),
        sa.Column("passing_yards", sa.Float(), nullable=True),
        sa.Column("passing_touchdowns", sa.Float(), nullable=True),
        sa.Column("interceptions", sa.Float(), nullable=True),
        sa.Column("sacks_taken", sa.Float(), nullable=True),
        sa.Column("rushing_attempts", sa.Float(), nullable=True),
        sa.Column("rushing_yards", sa.Float(), nullable=True),
        sa.Column("rushing_touchdowns", sa.Float(), nullable=True),
        sa.Column("long_rush", sa.Float(), nullable=True),
        sa.Column("receptions", sa.Float(), nullable=True),
        sa.Column("receiving_targets", sa.Float(), nullable=True),
        sa.Column("receiving_yards", sa.Float(), nullable=True),
        sa.Column("receiving_touchdowns", sa.Float(), nullable=True),
        sa.Column("long_reception", sa.Float(), nullable=True),
        sa.Column("kick_return_attempts", sa.Float(), nullable=True),
        sa.Column("kick_return_yards", sa.Float(), nullable=True),
        sa.Column("kick_return_touchdowns", sa.Float(), nullable=True),
        sa.Column("punt_return_attempts", sa.Float(), nullable=True),
        sa.Column("punt_return_yards", sa.Float(), nullable=True),
        sa.Column("punt_return_touchdowns", sa.Float(), nullable=True),
        sa.Column("field_goals_made", sa.Float(), nullable=True),
        sa.Column("field_goals_attempted", sa.Float(), nullable=True),
        sa.Column("field_goals_0_19", sa.Float(), nullable=True),
        sa.Column("field_goals_20_29", sa.Float(), nullable=True),
        sa.Column("field_goals_30_39", sa.Float(), nullable=True),
        sa.Column("field_goals_40_49", sa.Float(), nullable=True),
        sa.Column("field_goals_50_plus", sa.Float(), nullable=True),
        sa.Column("extra_points_made", sa.Float(), nullable=True),
        sa.Column("extra_points_attempted", sa.Float(), nullable=True),
        sa.Column("fumbles", sa.Float(), nullable=True),
        sa.Column("fumbles_lost", sa.Float(), nullable=True),
        sa.Column("fantasy_points", sa.Float(), nullable=True),
        sa.Column("fantasy_points_per_game", sa.Float(), nullable=True),
        sa.Column("scoring_rules_version", sa.String(length=80), nullable=True),
        sa.Column("source_response_hash", sa.String(length=64), nullable=True),
        sa.Column("parser_version", sa.String(length=40), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_labels", sa.JSON(), nullable=True),
        sa.Column("unknown_labels", sa.JSON(), nullable=True),
        sa.Column("is_final", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("player_id", "provider", "season", "season_type", name="uq_player_historical_stats_player_provider_season"),
    )
    op.create_index("ix_player_historical_stats_player_id", "player_historical_season_stats", ["player_id"])
    op.create_index("ix_player_historical_stats_provider_player", "player_historical_season_stats", ["provider", "provider_player_id"])
    op.create_index("ix_player_historical_stats_season", "player_historical_season_stats", ["season"])

    op.create_table(
        "historical_stat_import_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("requested_seasons", sa.JSON(), nullable=True),
        sa.Column("requested_player_ids", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("players_requested", sa.Integer(), nullable=False),
        sa.Column("players_succeeded", sa.Integer(), nullable=False),
        sa.Column("players_not_found", sa.Integer(), nullable=False),
        sa.Column("players_unmatched", sa.Integer(), nullable=False),
        sa.Column("players_failed", sa.Integer(), nullable=False),
        sa.Column("responses_reused", sa.Integer(), nullable=False),
        sa.Column("responses_fetched", sa.Integer(), nullable=False),
        sa.Column("rows_inserted", sa.Integer(), nullable=False),
        sa.Column("rows_updated", sa.Integer(), nullable=False),
        sa.Column("schema_failures", sa.Integer(), nullable=False),
        sa.Column("error_summary", sa.JSON(), nullable=True),
        sa.Column("triggered_by_user_id", sa.Integer(), nullable=True),
        sa.Column("trigger_type", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["triggered_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_historical_stat_import_runs_provider_status", "historical_stat_import_runs", ["provider", "status"])
    op.create_index("ix_historical_stat_import_runs_started_at", "historical_stat_import_runs", ["started_at"])


def downgrade() -> None:
    op.drop_index("ix_historical_stat_import_runs_started_at", table_name="historical_stat_import_runs")
    op.drop_index("ix_historical_stat_import_runs_provider_status", table_name="historical_stat_import_runs")
    op.drop_table("historical_stat_import_runs")
    op.drop_index("ix_player_historical_stats_season", table_name="player_historical_season_stats")
    op.drop_index("ix_player_historical_stats_provider_player", table_name="player_historical_season_stats")
    op.drop_index("ix_player_historical_stats_player_id", table_name="player_historical_season_stats")
    op.drop_table("player_historical_season_stats")
    op.drop_index("ix_provider_stat_cache_is_valid", table_name="provider_stat_cache")
    op.drop_index("ix_provider_stat_cache_expires_at", table_name="provider_stat_cache")
    op.drop_index("ix_provider_stat_cache_lookup", table_name="provider_stat_cache")
    op.drop_table("provider_stat_cache")
