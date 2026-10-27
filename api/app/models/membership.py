"""Provider-verified membership facts, separate from account/league ownership."""

from datetime import datetime
from uuid import uuid4
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from collegefootballfantasy_api.app.models import Base, TimestampMixin


class MembershipAccount(TimestampMixin, Base):
    __tablename__ = "membership_accounts"
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    apple_account_token: Mapped[str] = mapped_column(
        String(36), unique=True, default=lambda: str(uuid4())
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True
    )
    checkout_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    checkout_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    checkout_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    free_league_ids: Mapped[list] = mapped_column(JSON, default=list)
    free_league_season: Mapped[int | None] = mapped_column(Integer, nullable=True)


class MembershipSubscription(TimestampMixin, Base):
    __tablename__ = "membership_subscriptions"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_subscription_id",
            name="uq_membership_provider_subscription",
        ),
        CheckConstraint(
            "provider IN ('stripe','apple')", name="ck_membership_provider"
        ),
        CheckConstraint(
            "status IN ('active','past_due','canceled','expired','refunded','incomplete')",
            name="ck_membership_status",
        ),
        CheckConstraint("period_end >= period_start", name="ck_membership_period"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    # Keep the provider identifier tombstone after account deletion; never rebind it.
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    provider: Mapped[str] = mapped_column(String(10))
    provider_subscription_id: Mapped[str] = mapped_column(String(255))
    transaction_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20))
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False)
    provider_signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MembershipEvent(TimestampMixin, Base):
    __tablename__ = "membership_events"
    __table_args__ = (
        UniqueConstraint("provider", "event_id", name="uq_membership_provider_event"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(10))
    event_id: Mapped[str] = mapped_column(String(255))
    event_type: Mapped[str] = mapped_column(String(100))
    provider_subscription_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
