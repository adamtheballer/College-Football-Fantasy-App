from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class ProviderStatCache(TimestampMixin, Base):
    __tablename__ = "provider_stat_cache"
    __table_args__ = (
        UniqueConstraint("provider", "provider_player_id", "request_kind", "season_start", "season_end", "response_hash", name="uq_provider_stat_cache_response"),
        Index("ix_provider_stat_cache_lookup", "provider", "provider_player_id", "request_kind"),
        Index("ix_provider_stat_cache_expires_at", "expires_at"),
        Index("ix_provider_stat_cache_is_valid", "is_valid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_player_id: Mapped[str] = mapped_column(String(128), nullable=False)
    request_kind: Mapped[str] = mapped_column(String(80), nullable=False)
    season_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    season_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    response_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    provider_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    parser_version: Mapped[str] = mapped_column(String(40), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(40), nullable=False)
    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    validation_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PlayerHistoricalSeasonStat(TimestampMixin, Base):
    __tablename__ = "player_historical_season_stats"
    __table_args__ = (
        UniqueConstraint("player_id", "provider", "season", "season_type", name="uq_player_historical_stats_player_provider_season"),
        Index("ix_player_historical_stats_player_id", "player_id"),
        Index("ix_player_historical_stats_provider_player", "provider", "provider_player_id"),
        Index("ix_player_historical_stats_season", "season"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_player_id: Mapped[str] = mapped_column(String(128), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    season_type: Mapped[str] = mapped_column(String(30), nullable=False, default="regular")
    team_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider_team_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    team_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    position: Mapped[str | None] = mapped_column(String(20), nullable=True)
    games_played: Mapped[int | None] = mapped_column(Integer, nullable=True)
    games_started: Mapped[int | None] = mapped_column(Integer, nullable=True)

    passing_completions: Mapped[float | None] = mapped_column(Float, nullable=True)
    passing_attempts: Mapped[float | None] = mapped_column(Float, nullable=True)
    passing_yards: Mapped[float | None] = mapped_column(Float, nullable=True)
    passing_touchdowns: Mapped[float | None] = mapped_column(Float, nullable=True)
    interceptions: Mapped[float | None] = mapped_column(Float, nullable=True)
    sacks_taken: Mapped[float | None] = mapped_column(Float, nullable=True)

    rushing_attempts: Mapped[float | None] = mapped_column(Float, nullable=True)
    rushing_yards: Mapped[float | None] = mapped_column(Float, nullable=True)
    rushing_touchdowns: Mapped[float | None] = mapped_column(Float, nullable=True)
    long_rush: Mapped[float | None] = mapped_column(Float, nullable=True)

    receptions: Mapped[float | None] = mapped_column(Float, nullable=True)
    receiving_targets: Mapped[float | None] = mapped_column(Float, nullable=True)
    receiving_yards: Mapped[float | None] = mapped_column(Float, nullable=True)
    receiving_touchdowns: Mapped[float | None] = mapped_column(Float, nullable=True)
    long_reception: Mapped[float | None] = mapped_column(Float, nullable=True)

    kick_return_attempts: Mapped[float | None] = mapped_column(Float, nullable=True)
    kick_return_yards: Mapped[float | None] = mapped_column(Float, nullable=True)
    kick_return_touchdowns: Mapped[float | None] = mapped_column(Float, nullable=True)
    punt_return_attempts: Mapped[float | None] = mapped_column(Float, nullable=True)
    punt_return_yards: Mapped[float | None] = mapped_column(Float, nullable=True)
    punt_return_touchdowns: Mapped[float | None] = mapped_column(Float, nullable=True)

    field_goals_made: Mapped[float | None] = mapped_column(Float, nullable=True)
    field_goals_attempted: Mapped[float | None] = mapped_column(Float, nullable=True)
    field_goals_0_19: Mapped[float | None] = mapped_column(Float, nullable=True)
    field_goals_20_29: Mapped[float | None] = mapped_column(Float, nullable=True)
    field_goals_30_39: Mapped[float | None] = mapped_column(Float, nullable=True)
    field_goals_40_49: Mapped[float | None] = mapped_column(Float, nullable=True)
    field_goals_50_plus: Mapped[float | None] = mapped_column(Float, nullable=True)
    extra_points_made: Mapped[float | None] = mapped_column(Float, nullable=True)
    extra_points_attempted: Mapped[float | None] = mapped_column(Float, nullable=True)

    fumbles: Mapped[float | None] = mapped_column(Float, nullable=True)
    fumbles_lost: Mapped[float | None] = mapped_column(Float, nullable=True)

    fantasy_points: Mapped[float | None] = mapped_column(Float, nullable=True)
    fantasy_points_per_game: Mapped[float | None] = mapped_column(Float, nullable=True)
    scoring_rules_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source_response_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parser_version: Mapped[str] = mapped_column(String(40), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    provider_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_labels: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    unknown_labels: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_final: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    player = relationship("Player")


class HistoricalStatImportRun(TimestampMixin, Base):
    __tablename__ = "historical_stat_import_runs"
    __table_args__ = (
        Index("ix_historical_stat_import_runs_provider_status", "provider", "status"),
        Index("ix_historical_stat_import_runs_started_at", "started_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_seasons: Mapped[list | None] = mapped_column(JSON, nullable=True)
    requested_player_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="queued")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    players_requested: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    players_succeeded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    players_not_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    players_unmatched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    players_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    responses_reused: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    responses_fetched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_inserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    schema_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    triggered_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    trigger_type: Mapped[str] = mapped_column(String(40), nullable=False, default="manual")
