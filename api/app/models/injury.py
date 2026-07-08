from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class Injury(TimestampMixin, Base):
    __tablename__ = "injuries"
    __table_args__ = (
        Index("ix_injuries_player_id", "player_id"),
        Index("ix_injuries_season_week", "season", "week"),
        Index("ix_injuries_source_updated_at", "source_updated_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    season: Mapped[int] = mapped_column(Integer)
    week: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="FULL")
    normalized_status: Mapped[str] = mapped_column(String(20), default="healthy")
    injury: Mapped[str | None] = mapped_column(String(200), nullable=True)
    body_part: Mapped[str | None] = mapped_column(String(100), nullable=True)
    return_timeline: Mapped[str | None] = mapped_column(String(100), nullable=True)
    practice_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_game_time_decision: Mapped[bool] = mapped_column(Boolean, default=False)
    is_returning: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source: Mapped[str] = mapped_column(String(40), default="unknown")
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class InjuryHistory(TimestampMixin, Base):
    __tablename__ = "injury_history"
    __table_args__ = (
        UniqueConstraint(
            "player_id",
            "season",
            "week",
            "status",
            "injury",
            "source",
            name="uq_injury_history_player_week_state_source",
        ),
        Index("ix_injury_history_player_id", "player_id"),
        Index("ix_injury_history_season_week", "season", "week"),
        Index("ix_injury_history_source_updated_at", "source_updated_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    season: Mapped[int] = mapped_column(Integer)
    week: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="unknown")
    normalized_status: Mapped[str] = mapped_column(String(20), default="unknown")
    injury: Mapped[str | None] = mapped_column(String(200), nullable=True)
    body_part: Mapped[str | None] = mapped_column(String(100), nullable=True)
    return_timeline: Mapped[str | None] = mapped_column(String(100), nullable=True)
    practice_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source: Mapped[str] = mapped_column(String(40), default="unknown")
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
