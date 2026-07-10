from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class ProviderUnmatchedPlayerRow(TimestampMixin, Base):
    __tablename__ = "provider_unmatched_player_rows"
    __table_args__ = (
        Index("ix_provider_unmatched_rows_provider_week", "provider", "season", "week"),
        Index("ix_provider_unmatched_rows_status", "status"),
        Index("ix_provider_unmatched_rows_dedupe_hash", "dedupe_hash", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    provider_player_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    provider_player_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    provider_team: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reason: Mapped[str] = mapped_column(String(120), nullable=False)
    dedupe_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="open", nullable=False)
    mapped_player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id", ondelete="SET NULL"), nullable=True)
    resolved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_json: Mapped[dict] = mapped_column(JSON, default={})
