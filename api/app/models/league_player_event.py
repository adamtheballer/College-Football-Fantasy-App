from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class LeaguePlayerEvent(TimestampMixin, Base):
    """Immutable, league-scoped ownership and transaction history for a player."""

    __tablename__ = "league_player_events"
    __table_args__ = (
        UniqueConstraint("league_id", "event_key", name="uq_league_player_events_event_key"),
        Index("ix_league_player_events_league_player_occurred", "league_id", "player_id", "occurred_at"),
        Index("ix_league_player_events_league_occurred", "league_id", "occurred_at"),
        Index("ix_league_player_events_player_id", "player_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="RESTRICT"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # A source-derived idempotency key. It remains internal while allowing backfills and workers to retry safely.
    event_key: Mapped[str] = mapped_column(String(200), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    fantasy_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    from_fantasy_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    to_fantasy_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    manager_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    draft_id: Mapped[int | None] = mapped_column(ForeignKey("drafts.id", ondelete="SET NULL"), nullable=True)
    draft_pick_id: Mapped[int | None] = mapped_column(ForeignKey("draft_picks.id", ondelete="SET NULL"), nullable=True)
    trade_id: Mapped[int | None] = mapped_column(ForeignKey("trade_offers.id", ondelete="SET NULL"), nullable=True)
    waiver_claim_id: Mapped[int | None] = mapped_column(ForeignKey("waiver_claims.id", ondelete="SET NULL"), nullable=True)
    transaction_id: Mapped[int | None] = mapped_column(ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True)

    player_name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    position_snapshot: Mapped[str] = mapped_column(String(20), nullable=False)
    school_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    player_value_snapshot: Mapped[float | None] = mapped_column(Float, nullable=True)
    fantasy_team_name_snapshot: Mapped[str | None] = mapped_column(String(200), nullable=True)
    from_team_name_snapshot: Mapped[str | None] = mapped_column(String(200), nullable=True)
    to_team_name_snapshot: Mapped[str | None] = mapped_column(String(200), nullable=True)
    manager_name_snapshot: Mapped[str | None] = mapped_column(String(200), nullable=True)
    event_metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
