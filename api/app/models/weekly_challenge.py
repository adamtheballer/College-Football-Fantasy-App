"""App-wide competitions. Existing users, games and players remain canonical."""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class ChallengeRound(TimestampMixin, Base):
    __tablename__ = "challenge_rounds"
    __table_args__ = (UniqueConstraint("season", "week", name="uq_challenge_round_week"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    season: Mapped[int]
    week: Mapped[int]
    rollover_policy: Mapped[str] = mapped_column(String(60), default="matchup-display-v1")
    next_rollover_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WeeklyChallenge(TimestampMixin, Base):
    __tablename__ = "weekly_challenges"
    __table_args__ = (
        UniqueConstraint("round_id", "kind", "variant", name="uq_weekly_challenge_variant"),
        Index("ix_weekly_challenges_settlement", "status", "last_scored_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("challenge_rounds.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    variant: Mapped[str] = mapped_column(String(80), default="primary", server_default="primary")
    status: Mapped[str] = mapped_column(String(24), default="draft")
    version: Mapped[int] = mapped_column(default=0)
    rules_version: Mapped[str] = mapped_column(String(50), default="weekly-v1")
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lock_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_scored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_hash: Mapped[str | None] = mapped_column(String(64))
    cancellation_reason: Mapped[str | None] = mapped_column(String(500))


class ChallengeSlateGame(Base):
    __tablename__ = "challenge_slate_games"
    __table_args__ = (UniqueConstraint("challenge_id", "game_id", name="uq_challenge_slate_game"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    challenge_id: Mapped[int] = mapped_column(ForeignKey("weekly_challenges.id", ondelete="CASCADE"), index=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="RESTRICT"))
    snapshot: Mapped[dict] = mapped_column(JSON)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ChallengePoolPlayer(Base):
    __tablename__ = "challenge_pool_players"
    __table_args__ = (UniqueConstraint("challenge_id", "player_id", name="uq_challenge_pool_player"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    challenge_id: Mapped[int] = mapped_column(ForeignKey("weekly_challenges.id", ondelete="CASCADE"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="RESTRICT"))
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="RESTRICT"))
    snapshot: Mapped[dict] = mapped_column(JSON)


class ChallengeEntry(TimestampMixin, Base):
    __tablename__ = "challenge_entries"
    __table_args__ = (
        UniqueConstraint("challenge_id", "user_id", name="uq_challenge_official_entry"),
        Index("ix_challenge_entries_user", "user_id", "challenge_id"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    challenge_id: Mapped[int] = mapped_column(ForeignKey("weekly_challenges.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(20), default="draft")
    revision: Mapped[int] = mapped_column(default=0)
    # Validated against this instance's FK-backed, immutable slate/pool.
    selections: Mapped[list] = mapped_column(JSON, default=list)
    tiebreaker: Mapped[int | None]
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ChallengeDuel(TimestampMixin, Base):
    __tablename__ = "challenge_duels"
    __table_args__ = (
        UniqueConstraint("challenge_id", "low_user_id", "high_user_id", name="uq_challenge_duel_pair"),
        CheckConstraint("low_user_id < high_user_id", name="ck_challenge_duel_distinct"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    challenge_id: Mapped[int] = mapped_column(ForeignKey("weekly_challenges.id", ondelete="CASCADE"), index=True)
    inviter_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    invitee_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    low_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    high_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outcome: Mapped[str | None] = mapped_column(String(30))


class ChallengeDuelSeat(Base):
    """One ranked participation across BOTH inviter and invitee roles."""
    __tablename__ = "challenge_duel_seats"
    __table_args__ = (UniqueConstraint("challenge_id", "user_id", name="uq_challenge_duel_user"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    challenge_id: Mapped[int] = mapped_column(ForeignKey("weekly_challenges.id", ondelete="CASCADE"))
    duel_id: Mapped[int] = mapped_column(ForeignKey("challenge_duels.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))


class ChallengeScore(TimestampMixin, Base):
    __tablename__ = "challenge_scores"
    __table_args__ = (UniqueConstraint("entry_id", name="uq_challenge_score_entry"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("challenge_entries.id", ondelete="CASCADE"))
    raw_points: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    tiebreaker_error: Mapped[int | None]
    rank: Mapped[int | None]
    status: Mapped[str] = mapped_column(String(20))
    source_hash: Mapped[str] = mapped_column(String(64))
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class ChallengeAward(TimestampMixin, Base):
    """Current idempotent award; every correction is recorded in the audit ledger."""
    __tablename__ = "challenge_awards"
    __table_args__ = (
        UniqueConstraint("entry_id", name="uq_challenge_award_entry"),
        CheckConstraint("points >= 0 AND points <= 15", name="ck_challenge_award_points"),
        Index("ix_challenge_awards_round_user", "round_id", "user_id"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("challenge_entries.id", ondelete="CASCADE"))
    round_id: Mapped[int] = mapped_column(ForeignKey("challenge_rounds.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    points: Mapped[int]
    source_hash: Mapped[str] = mapped_column(String(64))
    revision: Mapped[int] = mapped_column(default=1)


class ChallengeRecognition(TimestampMixin, Base):
    __tablename__ = "challenge_recognitions"
    __table_args__ = (UniqueConstraint("round_id", "user_id", "code", name="uq_challenge_recognition"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("challenge_rounds.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(60))
    active: Mapped[bool] = mapped_column(default=True)


class ChallengeAudit(Base):
    __tablename__ = "challenge_audits"
    id: Mapped[int] = mapped_column(primary_key=True)
    challenge_id: Mapped[int] = mapped_column(ForeignKey("weekly_challenges.id", ondelete="RESTRICT"), index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(30))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    details: Mapped[dict] = mapped_column(JSON)
