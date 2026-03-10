from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class LeagueInvite(TimestampMixin, Base):
    __tablename__ = "league_invites"
    __table_args__ = (
        Index("ix_league_invites_code", "code"),
        Index("ix_league_invites_league_id", "league_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
