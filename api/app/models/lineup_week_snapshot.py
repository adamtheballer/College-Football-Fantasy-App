from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class LineupWeekSnapshot(TimestampMixin, Base):
    __tablename__ = "lineup_week_snapshots"
    __table_args__ = (
        UniqueConstraint("league_id", "team_id", "player_id", "season", "week", name="uq_lineup_snapshot_player_week"),
        Index("ix_lineup_snapshots_league_week", "league_id", "season", "week"),
        Index("ix_lineup_snapshots_team_week", "team_id", "season", "week"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    season: Mapped[int] = mapped_column(Integer)
    week: Mapped[int] = mapped_column(Integer)
    slot: Mapped[str] = mapped_column(String(50))
    is_starter: Mapped[bool] = mapped_column(Boolean, default=False)
    game_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
