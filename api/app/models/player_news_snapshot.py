from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from api.app.models import Base, TimestampMixin


class PlayerNewsSnapshot(TimestampMixin, Base):
    __tablename__ = "player_news_snapshots"
    __table_args__ = (
        UniqueConstraint("player_id", "season", name="uq_player_news_snapshots_player_season"),
        Index("ix_player_news_snapshots_player_id", "player_id"),
        Index("ix_player_news_snapshots_season", "season"),
        Index("ix_player_news_snapshots_verified", "verified_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    season: Mapped[int] = mapped_column(Integer)
    summary: Mapped[str] = mapped_column(String(1200))
    source_type: Mapped[str] = mapped_column(String(40), default="verified_override")
    is_transfer: Mapped[bool] = mapped_column(Boolean, default=False)
    from_school: Mapped[str | None] = mapped_column(String(120), nullable=True)
    to_school: Mapped[str | None] = mapped_column(String(120), nullable=True)
    expected_role: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_urls: Mapped[list] = mapped_column(JSON, default=list)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
