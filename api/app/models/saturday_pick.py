from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class SaturdayPickContest(TimestampMixin, Base):
    """The weekly, globally available Saturday Pick 6 contest.

    The contest is intentionally independent of a fantasy league.  A user can
    save one pick per contest and may replace it only while the contest is open.
    """

    __tablename__ = "saturday_pick_contests"
    __table_args__ = (
        UniqueConstraint("season", "week_number", name="uq_saturday_pick_contest_season_week"),
        Index("ix_saturday_pick_contests_status_lock", "status", "lock_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    week_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False, default="Saturday Pick 6")
    contest_position: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="DRAFT")
    lock_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scoring_policy_version: Mapped[str] = mapped_column(String(64), nullable=False, default="STANDARD_V1")
    winning_player_ids_json: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    sponsor_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    sponsor_logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sponsor_offer_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sponsor_code: Mapped[str | None] = mapped_column(String(160), nullable=True)
    sponsor_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sponsor_terms: Mapped[str | None] = mapped_column(String(1_000), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class SaturdayPickPlayer(TimestampMixin, Base):
    __tablename__ = "saturday_pick_players"
    __table_args__ = (
        UniqueConstraint("contest_id", "player_id", name="uq_saturday_pick_player_contest_player"),
        UniqueConstraint("contest_id", "sort_order", name="uq_saturday_pick_player_contest_sort_order"),
        Index("ix_saturday_pick_players_contest", "contest_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    contest_id: Mapped[int] = mapped_column(ForeignKey("saturday_pick_contests.id", ondelete="CASCADE"))
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="RESTRICT"))
    canonical_position: Mapped[str] = mapped_column(String(8), nullable=False)
    player_name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    school_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    opponent_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    game_id: Mapped[int | None] = mapped_column(ForeignKey("games.id", ondelete="SET NULL"), nullable=True)
    game_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    projected_points: Mapped[float | None] = mapped_column(Float, nullable=True)
    live_points: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_points: Mapped[float | None] = mapped_column(Float, nullable=True)
    scoring_status: Mapped[str] = mapped_column(String(32), nullable=False, default="NOT_STARTED")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)


class SaturdayPickEntry(TimestampMixin, Base):
    __tablename__ = "saturday_pick_entries"
    __table_args__ = (
        UniqueConstraint("contest_id", "user_id", name="uq_saturday_pick_entry_contest_user"),
        Index("ix_saturday_pick_entries_contest", "contest_id"),
        Index("ix_saturday_pick_entries_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    contest_id: Mapped[int] = mapped_column(ForeignKey("saturday_pick_contests.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    selected_pick_player_id: Mapped[int] = mapped_column(
        ForeignKey("saturday_pick_players.id", ondelete="RESTRICT")
    )
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_winner: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reward_unlocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SponsorRewardEvent(TimestampMixin, Base):
    __tablename__ = "sponsor_reward_events"
    __table_args__ = (Index("ix_sponsor_reward_events_contest_user", "contest_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    contest_id: Mapped[int] = mapped_column(ForeignKey("saturday_pick_contests.id", ondelete="CASCADE"))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    sponsor_name: Mapped[str] = mapped_column(String(160), nullable=False)
    placement: Mapped[str | None] = mapped_column(String(80), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
