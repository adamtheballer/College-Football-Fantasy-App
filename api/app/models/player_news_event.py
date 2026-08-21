from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class PlayerNewsEvent(TimestampMixin, Base):
    """Classified roster/depth-chart news awaiting or carrying human review."""

    __tablename__ = "player_news_events"
    __table_args__ = (
        Index("ix_player_news_events_player_season_week", "player_id", "season", "week"),
        Index("ix_player_news_events_effective_window", "season", "effective_from_week", "effective_until_week"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    related_player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id", ondelete="SET NULL"), nullable=True)
    current_team_id: Mapped[int | None] = mapped_column(ForeignKey("college_teams.id", ondelete="SET NULL"), nullable=True)
    season: Mapped[int] = mapped_column(Integer)
    week: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(40))
    role: Mapped[str | None] = mapped_column(String(40), nullable=True)
    usage_direction: Mapped[str | None] = mapped_column(String(20), nullable=True)
    role_score_delta: Mapped[float] = mapped_column(Float, default=0.0)
    source: Mapped[str] = mapped_column(String(200))
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_reliability: Mapped[float] = mapped_column(Float, default=0.5)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_from_week: Mapped[int] = mapped_column(Integer)
    effective_until_week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
