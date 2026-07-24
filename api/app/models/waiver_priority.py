from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class WaiverPriority(TimestampMixin, Base):
    __tablename__ = "waiver_priorities"
    __table_args__ = (
        UniqueConstraint("league_id", "team_id", name="uq_waiver_priorities_league_team"),
        UniqueConstraint("league_id", "priority", name="uq_waiver_priorities_league_priority"),
        Index("ix_waiver_priorities_league_priority", "league_id", "priority"),
        CheckConstraint("priority > 0", name="ck_waiver_priorities_priority_positive"),
        CheckConstraint("faab_budget >= 0", name="ck_waiver_priorities_faab_budget_nonnegative"),
        CheckConstraint("faab_spent >= 0", name="ck_waiver_priorities_faab_spent_nonnegative"),
        CheckConstraint("faab_spent <= faab_budget", name="ck_waiver_priorities_faab_remaining_nonnegative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    priority: Mapped[int] = mapped_column(Integer)
    faab_budget: Mapped[int] = mapped_column(Integer, default=100)
    faab_spent: Mapped[int] = mapped_column(Integer, default=0)

    @property
    def faab_remaining(self) -> int:
        return int(self.faab_budget or 0) - int(self.faab_spent or 0)
