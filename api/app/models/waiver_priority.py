from sqlalchemy import ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class WaiverPriority(TimestampMixin, Base):
    __tablename__ = "waiver_priority"
    __table_args__ = (
        UniqueConstraint("league_id", "team_id", name="uq_waiver_priority_league_team"),
        Index("ix_waiver_priority_league_id", "league_id"),
        Index("ix_waiver_priority_team_id", "team_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    priority: Mapped[int] = mapped_column(Integer)
    faab_remaining: Mapped[int] = mapped_column(Integer, default=100)
