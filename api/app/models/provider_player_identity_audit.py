from sqlalchemy import JSON, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class ProviderPlayerIdentityAudit(TimestampMixin, Base):
    __tablename__ = "provider_player_identity_audits"
    __table_args__ = (
        Index("ix_provider_identity_audits_provider_week", "provider", "season", "week"),
        Index("ix_provider_identity_audits_match_type", "match_type"),
        Index("ix_provider_identity_audits_player_id", "player_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id", ondelete="SET NULL"), nullable=True)
    provider_player_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    provider_player_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    provider_team: Mapped[str | None] = mapped_column(String(200), nullable=True)
    match_type: Mapped[str] = mapped_column(String(80), nullable=False)
    confidence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    raw_json: Mapped[dict] = mapped_column(JSON, default={})
