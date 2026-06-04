from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from api.app.models import Base, TimestampMixin


class Lineup(TimestampMixin, Base):
    __tablename__ = "lineups"
    __table_args__ = (
        UniqueConstraint("league_id", "team_id", "season", "week", name="uq_lineups_team_season_week"),
        Index("ix_lineups_league_week", "league_id", "season", "week"),
        Index("ix_lineups_team_week", "team_id", "season", "week"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    season: Mapped[int] = mapped_column(Integer)
    week: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="editable")
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LineupEntry(TimestampMixin, Base):
    __tablename__ = "lineup_entries"
    __table_args__ = (
        UniqueConstraint("lineup_id", "player_id", name="uq_lineup_entries_lineup_player"),
        Index("ix_lineup_entries_lineup_id", "lineup_id"),
        Index("ix_lineup_entries_player_id", "player_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    lineup_id: Mapped[int] = mapped_column(ForeignKey("lineups.id", ondelete="CASCADE"))
    roster_entry_id: Mapped[int | None] = mapped_column(
        ForeignKey("roster_entries.id", ondelete="SET NULL"),
        nullable=True,
    )
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    slot: Mapped[str] = mapped_column(String(50))
    is_starter: Mapped[bool] = mapped_column(Boolean, default=True)
