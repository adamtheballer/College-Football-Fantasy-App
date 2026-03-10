from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class League(TimestampMixin, Base):
    __tablename__ = "leagues"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=False, index=True)
    platform: Mapped[str] = mapped_column(String(50), index=True, default="custom")
    scoring_type: Mapped[str] = mapped_column(String(50), default="espn_full_ppr")
    commissioner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    season_year: Mapped[int] = mapped_column(Integer, default=2026)
    max_teams: Mapped[int] = mapped_column(Integer, default=12)
    is_private: Mapped[bool] = mapped_column(Boolean, default=True)
    invite_code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    icon_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pre_draft")

    teams = relationship("Team", back_populates="league", cascade="all, delete-orphan")
