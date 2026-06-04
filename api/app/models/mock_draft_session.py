from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from api.app.models import Base, TimestampMixin


class MockDraftSession(TimestampMixin, Base):
    __tablename__ = "mock_draft_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    commissioner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    host_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    invite_code: Mapped[str | None] = mapped_column(String(128), unique=True, index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(200), default="Mock Draft")
    mode: Mapped[str] = mapped_column("mode", String(30), default="public_multiplayer", index=True, quote=True)
    status: Mapped[str] = mapped_column(String(30), default="filling", index=True)
    manager_count: Mapped[int] = mapped_column(Integer, default=12)
    team_count: Mapped[int] = mapped_column(Integer, default=12)
    round_count: Mapped[int] = mapped_column(Integer, default=13)
    draft_type: Mapped[str] = mapped_column(String(30), default="snake")
    pick_timer_seconds: Mapped[int] = mapped_column(Integer, default=90)
    roster_slots_json: Mapped[dict] = mapped_column(JSON, default=dict)
    scoring_json: Mapped[dict] = mapped_column(JSON, default=dict)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    draft_datetime_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    intermission_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    intermission_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    current_pick_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_pick_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_overall_pick: Mapped[int] = mapped_column(Integer, default=1)
    draft_order_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    player_pool: Mapped[str] = mapped_column(String(60), default="power4")
    scoring_type: Mapped[str] = mapped_column(String(80), default="espn_full_ppr")
    bot_difficulty: Mapped[str] = mapped_column(String(60), default="basic")
    history_email_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    should_preserve_history: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
