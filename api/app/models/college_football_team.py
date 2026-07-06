from sqlalchemy import Index, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class CollegeFootballTeam(TimestampMixin, Base):
    __tablename__ = "college_football_teams"
    __table_args__ = (
        UniqueConstraint("provider", "external_id", name="uq_cfb_teams_provider_external_id"),
        Index("ix_cfb_teams_name", "name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(50), default="espn", nullable=False)
    external_id: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    short_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    abbreviation: Mapped[str | None] = mapped_column(String(20), nullable=True)
    location: Mapped[str | None] = mapped_column(String(120), nullable=True)
    conference: Mapped[str | None] = mapped_column(String(80), nullable=True)
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    alternate_color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    logos: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    raw_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
