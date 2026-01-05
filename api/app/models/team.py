from sqlalchemy import ForeignKey, String, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class Team(TimestampMixin, Base):
    __tablename__ = "teams"
    __table_args__ = (
        UniqueConstraint("league_id", "name", name="uq_team_league_name"),
        Index("ix_teams_league_id", "league_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    owner_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    league = relationship("League", back_populates="teams")
    roster_entries = relationship("RosterEntry", back_populates="team", cascade="all, delete-orphan")
