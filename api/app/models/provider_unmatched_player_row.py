from sqlalchemy import JSON, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class ProviderUnmatchedPlayerRow(TimestampMixin, Base):
    __tablename__ = "provider_unmatched_player_rows"
    __table_args__ = (
        Index("ix_provider_unmatched_rows_provider_week", "provider", "season", "week"),
        Index("ix_provider_unmatched_rows_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    provider_player_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    provider_player_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    provider_team: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reason: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="open", nullable=False)
    raw_json: Mapped[dict] = mapped_column(JSON, default={})
