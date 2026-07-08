from sqlalchemy import Boolean, ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class Watchlist(TimestampMixin, Base):
    __tablename__ = "watchlists"
    __table_args__ = (
        Index("ix_watchlists_user_id", "user_id"),
        Index("ix_watchlists_league_id", "league_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    league_id: Mapped[int | None] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"), nullable=True)
    name: Mapped[str] = mapped_column(nullable=False)

    players = relationship("WatchlistPlayer", back_populates="watchlist", cascade="all, delete-orphan")


class WatchlistPlayer(TimestampMixin, Base):
    __tablename__ = "watchlist_players"
    __table_args__ = (
        UniqueConstraint("watchlist_id", "player_id", name="uq_watchlist_players_watchlist_player"),
        Index("ix_watchlist_players_watchlist_id", "watchlist_id"),
        Index("ix_watchlist_players_player_id", "player_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    watchlist_id: Mapped[int] = mapped_column(ForeignKey("watchlists.id", ondelete="CASCADE"))
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=3)
    tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    alert_available: Mapped[bool] = mapped_column(Boolean, default=True)
    alert_injury: Mapped[bool] = mapped_column(Boolean, default=True)
    alert_projection: Mapped[bool] = mapped_column(Boolean, default=True)
    alert_ownership: Mapped[bool] = mapped_column(Boolean, default=True)
    alert_matchup: Mapped[bool] = mapped_column(Boolean, default=True)

    watchlist = relationship("Watchlist", back_populates="players")
    player = relationship("Player")
