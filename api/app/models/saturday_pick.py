from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class SaturdayPickContest(TimestampMixin, Base):
    __tablename__ = "saturday_pick_contests"
    __table_args__ = (
        UniqueConstraint("season", "week_number", name="uq_saturday_pick_contest_season_week"),
        Index("ix_saturday_pick_contests_status_lock", "status", "lock_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    week_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False, default="Saturday Pick 6")
    contest_position: Mapped[str] = mapped_column(String(4), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT")
    lock_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scoring_policy_version: Mapped[str] = mapped_column(String(60), nullable=False, default="STANDARD_V1")
    sponsor_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    sponsor_logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sponsor_offer_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sponsor_code: Mapped[str | None] = mapped_column(String(160), nullable=True)
    sponsor_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sponsor_terms: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    winning_player_ids_json: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    position_overridden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    override_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    position_override_actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    position_overridden_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SaturdayPickPlayer(TimestampMixin, Base):
    __tablename__ = "saturday_pick_players"
    __table_args__ = (
        UniqueConstraint("contest_id", "player_id", name="uq_saturday_pick_player_contest_player"),
        UniqueConstraint("contest_id", "sort_order", name="uq_saturday_pick_player_contest_sort"),
        Index("ix_saturday_pick_players_contest", "contest_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    contest_id: Mapped[int] = mapped_column(ForeignKey("saturday_pick_contests.id", ondelete="CASCADE"), nullable=False)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="RESTRICT"), nullable=False)
    canonical_position: Mapped[str] = mapped_column(String(4), nullable=False)
    player_name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    school_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    opponent_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    game_id: Mapped[int | None] = mapped_column(ForeignKey("games.id", ondelete="SET NULL"), nullable=True)
    game_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    projected_points: Mapped[float | None] = mapped_column(Float, nullable=True)
    live_points: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_points: Mapped[float | None] = mapped_column(Float, nullable=True)
    scoring_status: Mapped[str] = mapped_column(String(20), nullable=False, default="SCHEDULED")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)


class SaturdayPickEntry(TimestampMixin, Base):
    __tablename__ = "saturday_pick_entries"
    __table_args__ = (
        UniqueConstraint("contest_id", "user_id", name="uq_saturday_pick_entry_contest_user"),
        Index("ix_saturday_pick_entries_contest", "contest_id"),
        Index("ix_saturday_pick_entries_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    contest_id: Mapped[int] = mapped_column(ForeignKey("saturday_pick_contests.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    selected_pick_player_id: Mapped[int] = mapped_column(ForeignKey("saturday_pick_players.id", ondelete="RESTRICT"), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_winner: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    winner_determined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reward_unlocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reward_claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SponsorRewardEvent(TimestampMixin, Base):
    __tablename__ = "sponsor_reward_events"
    __table_args__ = (Index("ix_sponsor_reward_events_contest_user", "contest_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    contest_id: Mapped[int] = mapped_column(ForeignKey("saturday_pick_contests.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    sponsor_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    placement: Mapped[str | None] = mapped_column(String(100), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
