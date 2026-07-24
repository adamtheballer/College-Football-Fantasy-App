from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class WaiverClaim(TimestampMixin, Base):
    __tablename__ = "waiver_claims"
    __table_args__ = (
        Index("ix_waiver_claims_league_status", "league_id", "status"),
        Index("ix_waiver_claims_team_status", "team_id", "status"),
        Index("ix_waiver_claims_add_player", "league_id", "add_player_id"),
        Index("ix_waiver_claims_process_after", "process_after"),
        Index("ix_waiver_claims_period_status", "waiver_period_id", "status"),
        Index("ix_waiver_claims_window_status", "league_id", "processing_window_id", "status"),
        CheckConstraint("faab_bid >= 0", name="ck_waiver_claims_faab_bid_nonnegative"),
        CheckConstraint("preference_order > 0", name="ck_waiver_claims_preference_order_positive"),
        CheckConstraint("status IN ('pending', 'won', 'lost', 'cancelled', 'invalid', 'insufficient_budget', 'roster_full', 'player_unavailable', 'skipped', 'failed')", name="ck_waiver_claims_status"),
        Index(
            "uq_waiver_claims_pending_team_period_preference",
            "team_id",
            "waiver_period_id",
            "preference_order",
            unique=True,
            postgresql_where=text("status = 'pending'"),
            sqlite_where=text("status = 'pending'"),
        ),
        Index(
            "uq_waiver_claims_pending_team_period_player",
            "team_id",
            "waiver_period_id",
            "add_player_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
            sqlite_where=text("status = 'pending'"),
        ),
        Index(
            "uq_waiver_claims_player_period_winner",
            "league_id",
            "add_player_id",
            "waiver_period_id",
            unique=True,
            postgresql_where=text("status = 'won'"),
            sqlite_where=text("status = 'won'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    add_player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    drop_roster_entry_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    drop_player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id", ondelete="SET NULL"), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    season: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processing_week: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processing_window_id: Mapped[str] = mapped_column(String(120), nullable=False, default="legacy")
    waiver_period_id: Mapped[int] = mapped_column(ForeignKey("waiver_periods.id", ondelete="RESTRICT"), nullable=False)
    processing_run_id: Mapped[int | None] = mapped_column(ForeignKey("waiver_processing_runs.id", ondelete="SET NULL"), nullable=True)
    preference_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    priority_snapshot: Mapped[int | None] = mapped_column(Integer, nullable=True)
    faab_bid: Mapped[int] = mapped_column(Integer, default=0)
    winning_bid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prior_priority: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resulting_priority: Mapped[int | None] = mapped_column(Integer, nullable=True)
    process_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
