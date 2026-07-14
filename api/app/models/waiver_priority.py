from sqlalchemy import ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class WaiverPriority(TimestampMixin, Base):
    __tablename__ = "waiver_priorities"
    __table_args__ = (
        UniqueConstraint("league_id", "team_id", name="uq_waiver_priorities_league_team"),
        Index("ix_waiver_priorities_league_priority", "league_id", "priority"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    priority: Mapped[int] = mapped_column(Integer)
    faab_budget: Mapped[int] = mapped_column(Integer, default=100)
    faab_spent: Mapped[int] = mapped_column(Integer, default=0)

    @property
    def faab_remaining(self) -> int:
        return max(0, int(self.faab_budget or 0) - int(self.faab_spent or 0))
