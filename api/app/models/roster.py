from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class RosterEntry(TimestampMixin, Base):
    __tablename__ = "roster_entries"
    __table_args__ = (
        UniqueConstraint("team_id", "player_id", name="uq_roster_team_player"),
        Index("ix_roster_entries_team_id", "team_id"),
        Index("ix_roster_entries_player_id", "player_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    slot: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50))

    team = relationship("Team", back_populates="roster_entries")
    player = relationship("Player", back_populates="roster_entries")
