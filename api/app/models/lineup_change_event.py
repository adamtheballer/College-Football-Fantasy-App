from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class LineupChangeEvent(TimestampMixin, Base):
    __tablename__ = "lineup_change_events"
    __table_args__ = (
        Index("ix_lineup_change_events_team_week", "team_id", "week"),
        Index("ix_lineup_change_events_player_id", "player_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    week: Mapped[int] = mapped_column(Integer)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    from_slot: Mapped[str] = mapped_column(String(50))
    to_slot: Mapped[str] = mapped_column(String(50))
    lock_state: Mapped[str] = mapped_column(String(50))
    changed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
