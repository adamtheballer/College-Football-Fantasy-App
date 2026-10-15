"""Provider game history, separate from authoritative live fantasy scoring."""
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from collegefootballfantasy_api.app.models import Base, TimestampMixin

class PlayerHistoricalGameStat(TimestampMixin, Base):
    __tablename__ = "player_historical_game_stats"
    __table_args__ = (
        UniqueConstraint("player_id", "season", "provider", "provider_event_id", name="uq_historical_player_game"),
        CheckConstraint("week >= 0", name="ck_historical_player_game_week"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    season_type: Mapped[str] = mapped_column(String(30), nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_player_id: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_team_id: Mapped[str] = mapped_column(String(128), nullable=False)
    team_name: Mapped[str] = mapped_column(String(200), nullable=False)
    opponent_name: Mapped[str] = mapped_column(String(200), nullable=False)
    kickoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    location: Mapped[str] = mapped_column(String(30), nullable=False)
    result: Mapped[str] = mapped_column(String(80), nullable=False)
    position: Mapped[str] = mapped_column(String(20), nullable=False)
    stats: Mapped[dict] = mapped_column(JSON, nullable=False)
    source_response_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_url: Mapped[str] = mapped_column(String(500), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
