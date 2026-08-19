from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class LivePlayerProjection(TimestampMixin, Base):
    """One deterministic player projection for one accepted provider snapshot.

    The output is deliberately league-independent: projected stats are scored
    with each league's locked scoring rules only when a matchup is read.
    """

    __tablename__ = "live_player_projections"
    __table_args__ = (
        UniqueConstraint(
            "player_id", "game_id", "provider_snapshot_hash",
            name="uq_live_player_projection_snapshot",
        ),
        Index("ix_live_player_projections_week_player", "season", "week", "player_id"),
        Index("ix_live_player_projections_game_snapshot", "game_id", "provider_snapshot_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"), nullable=False)
    pregame_projection_id: Mapped[int | None] = mapped_column(
        ForeignKey("weekly_projections.id", ondelete="SET NULL"), nullable=True
    )
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    projection_status: Mapped[str] = mapped_column(String(24), nullable=False)
    game_period: Mapped[int | None] = mapped_column(Integer, nullable=True)
    game_clock: Mapped[str | None] = mapped_column(String(32), nullable=True)
    game_progress: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_stats_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    projected_final_stats_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    projected_remaining_stats_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    projected_remaining_fantasy_points: Mapped[float | None] = mapped_column(Float, nullable=True)
    observability_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    fallback_reason: Mapped[str | None] = mapped_column(String(120), nullable=True)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
