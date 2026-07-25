from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class PlayerWeeklyContext(TimestampMixin, Base):
    """The reviewed projection context carried from one week into the next."""

    __tablename__ = "player_weekly_contexts"
    __table_args__ = (
        UniqueConstraint("player_id", "season", "week", name="uq_player_weekly_contexts_player_season_week"),
        Index("ix_player_weekly_contexts_season_week", "season", "week"),
        Index("ix_player_weekly_contexts_team_season_week", "current_team_id", "season", "week"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    season: Mapped[int] = mapped_column(Integer)
    week: Mapped[int] = mapped_column(Integer)
    current_team_id: Mapped[int | None] = mapped_column(ForeignKey("college_teams.id", ondelete="SET NULL"), nullable=True)
    role: Mapped[str | None] = mapped_column(String(40), nullable=True)
    role_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    projected_usage_share: Mapped[float | None] = mapped_column(Float, nullable=True)
    usage_confidence: Mapped[float] = mapped_column(Float, default=0.5)
    availability_status: Mapped[str] = mapped_column(String(20), default="UNKNOWN")
    availability_multiplier: Mapped[float] = mapped_column(Float, default=0.75)
    availability_event_id: Mapped[int | None] = mapped_column(ForeignKey("player_availability_events.id", ondelete="SET NULL"), nullable=True)
    news_event_id: Mapped[int | None] = mapped_column(ForeignKey("player_news_events.id", ondelete="SET NULL"), nullable=True)
    source_context_week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    manual_review_required: Mapped[bool] = mapped_column(Boolean, default=False)
    change_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
