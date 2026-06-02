from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class Team(TimestampMixin, Base):
    __tablename__ = "teams"
    __table_args__ = (
        UniqueConstraint("league_id", "name", name="uq_team_league_name"),
        UniqueConstraint("league_id", "owner_user_id", name="uq_team_league_owner"),
        Index("ix_teams_league_id", "league_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    owner_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    waiver_priority: Mapped[int] = mapped_column(Integer, default=0)
    faab_balance: Mapped[int] = mapped_column(Integer, default=100)

    league = relationship("League", back_populates="teams")
    roster_entries = relationship("RosterEntry", back_populates="team", cascade="all, delete-orphan")
