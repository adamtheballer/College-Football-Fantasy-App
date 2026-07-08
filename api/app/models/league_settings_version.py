from sqlalchemy import ForeignKey, Index, Integer, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class LeagueSettingsVersion(TimestampMixin, Base):
    __tablename__ = "league_settings_versions"
    __table_args__ = (
        UniqueConstraint("league_id", "version", name="uq_league_settings_versions_league_version"),
        Index("ix_league_settings_versions_league_id", "league_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer)
    settings_json: Mapped[dict] = mapped_column(JSON, default={})
    effective_season: Mapped[int] = mapped_column(Integer)
    effective_week: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
