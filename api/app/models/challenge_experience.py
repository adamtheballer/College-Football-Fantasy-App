"""Mode-specific facts attached to the existing competition/entry lifecycle."""

from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from collegefootballfantasy_api.app.models import Base, TimestampMixin


class ChallengeCreator(TimestampMixin, Base):
    __tablename__ = "challenge_creators"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(500), default="")
    logo_url: Mapped[str | None] = mapped_column(Text)
    links: Mapped[dict] = mapped_column(JSON, default=dict)
    authorized: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    owner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class ChallengeSurvivorSeries(TimestampMixin, Base):
    __tablename__ = "challenge_survivor_series"
    __table_args__ = (
        CheckConstraint(
            "start_week >= 1 AND end_week >= start_week AND end_week <= 15",
            name="ck_survivor_series_weeks",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    season: Mapped[int] = mapped_column(index=True)
    start_week: Mapped[int]
    end_week: Mapped[int]
    entry_open_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    first_lock_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class ChallengeExperience(TimestampMixin, Base):
    __tablename__ = "challenge_experiences"
    challenge_id: Mapped[int] = mapped_column(
        ForeignKey("weekly_challenges.id", ondelete="CASCADE"), primary_key=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    creator_id: Mapped[int | None] = mapped_column(
        ForeignKey("challenge_creators.id", ondelete="RESTRICT"), index=True
    )
    series_id: Mapped[int | None] = mapped_column(
        ForeignKey("challenge_survivor_series.id", ondelete="RESTRICT"), index=True
    )
    entry_open_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ChallengeSalary(Base):
    __tablename__ = "challenge_salaries"
    __table_args__ = (
        UniqueConstraint(
            "challenge_id", "player_id", name="uq_challenge_salary_player"
        ),
        CheckConstraint(
            "salary > 0 AND salary <= 100", name="ck_challenge_salary_budget"
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    challenge_id: Mapped[int] = mapped_column(
        ForeignKey("weekly_challenges.id", ondelete="CASCADE"), index=True
    )
    player_id: Mapped[int] = mapped_column(
        ForeignKey("players.id", ondelete="RESTRICT")
    )
    salary: Mapped[Decimal] = mapped_column(Numeric(6, 2))


class ChallengeCreatorPick(Base):
    __tablename__ = "challenge_creator_picks"
    __table_args__ = (
        UniqueConstraint("challenge_id", "game_id", name="uq_challenge_creator_pick"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    challenge_id: Mapped[int] = mapped_column(
        ForeignKey("weekly_challenges.id", ondelete="CASCADE"), index=True
    )
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="RESTRICT"))
    team: Mapped[str] = mapped_column(String(200))


class ChallengeFanMembership(TimestampMixin, Base):
    __tablename__ = "challenge_fan_memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "season", "week", name="uq_challenge_fan_week"),
        Index("ix_challenge_fan_school_week", "season", "week", "school_id"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    school_id: Mapped[int] = mapped_column(
        ForeignKey("college_teams.id", ondelete="RESTRICT")
    )
    season: Mapped[int]
    week: Mapped[int]
    # Freeze display/conference membership alongside each week's allegiance.
    school_name: Mapped[str] = mapped_column(String(200))
    conference: Mapped[str] = mapped_column(String(50))


class ChallengeEntrySchool(Base):
    __tablename__ = "challenge_entry_schools"
    entry_id: Mapped[int] = mapped_column(
        ForeignKey("challenge_entries.id", ondelete="CASCADE"), primary_key=True
    )
    membership_id: Mapped[int] = mapped_column(
        ForeignKey("challenge_fan_memberships.id", ondelete="RESTRICT"), index=True
    )


class ChallengeSurvivorEnrollment(TimestampMixin, Base):
    __tablename__ = "challenge_survivor_enrollments"
    __table_args__ = (
        UniqueConstraint("series_id", "user_id", name="uq_survivor_series_user"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    series_id: Mapped[int] = mapped_column(
        ForeignKey("challenge_survivor_series.id", ondelete="RESTRICT"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))


class ChallengeSurvivorPick(TimestampMixin, Base):
    __tablename__ = "challenge_survivor_picks"
    __table_args__ = (
        UniqueConstraint("enrollment_id", "week", name="uq_survivor_pick_week"),
        UniqueConstraint("enrollment_id", "school_key", name="uq_survivor_pick_school"),
    )
    entry_id: Mapped[int] = mapped_column(
        ForeignKey("challenge_entries.id", ondelete="CASCADE"), primary_key=True
    )
    enrollment_id: Mapped[int] = mapped_column(
        ForeignKey("challenge_survivor_enrollments.id", ondelete="CASCADE"), index=True
    )
    week: Mapped[int]
    school_key: Mapped[str] = mapped_column(String(200))
    outcome: Mapped[str] = mapped_column(String(24), default="pending")


class ChallengeGameDecision(TimestampMixin, Base):
    __tablename__ = "challenge_game_decisions"
    __table_args__ = (
        UniqueConstraint("challenge_id", "game_id", name="uq_challenge_game_decision"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    challenge_id: Mapped[int] = mapped_column(
        ForeignKey("weekly_challenges.id", ondelete="CASCADE"), index=True
    )
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="RESTRICT"))
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    reason: Mapped[str] = mapped_column(String(500))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class ChallengeEvent(Base):
    __tablename__ = "challenge_events"
    __table_args__ = (
        Index("ix_challenge_events_analytics", "challenge_id", "event_type", "at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    dedupe_key: Mapped[str] = mapped_column(String(180), unique=True)
    challenge_id: Mapped[int | None] = mapped_column(
        ForeignKey("weekly_challenges.id", ondelete="CASCADE")
    )
    creator_id: Mapped[int | None] = mapped_column(
        ForeignKey("challenge_creators.id", ondelete="SET NULL")
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    event_type: Mapped[str] = mapped_column(String(30))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ChallengeManagementAudit(Base):
    __tablename__ = "challenge_management_audits"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    resource: Mapped[str] = mapped_column(String(40))
    resource_id: Mapped[int]
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    details: Mapped[dict] = mapped_column(JSON)


class ChallengeAnalyticsPreference(TimestampMixin, Base):
    __tablename__ = "challenge_analytics_preferences"
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
