from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class BetaAccessCode(TimestampMixin, Base):
    """A non-reversible early-access code record.

    Raw codes are intentionally never persisted.  The keyed HMAC is sufficient
    for exact lookup while keeping backups, logs, and database reads from
    becoming a source of usable beta credentials.
    """

    __tablename__ = "beta_access_codes"
    __table_args__ = (
        Index("ix_beta_access_codes_state_expires", "state", "reservation_expires_at"),
        Index("ix_beta_access_codes_source_status", "source_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_waitlist_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True, index=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    code_hmac: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="AVAILABLE", server_default="AVAILABLE")
    source_status: Mapped[str] = mapped_column(String(32), nullable=False, default="READY_SENT")
    source_waitlist_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    discount_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    access_code_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    email_delivery_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email_delivery_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    email_delivery_provider_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email_delivery_attempt_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    email_delivery_last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    manual_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    reserved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reservation_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reservation_nonce_hmac: Mapped[str | None] = mapped_column(String(128), nullable=True)
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    redeemed_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), unique=True, nullable=True, index=True
    )


class BetaAccessAuditEvent(Base):
    """Append-only audit metadata; never stores raw e-mail addresses or codes."""

    __tablename__ = "beta_access_audit_events"
    __table_args__ = (
        Index("ix_beta_access_audit_events_code_created", "beta_access_code_id", "created_at"),
        Index("ix_beta_access_audit_events_action_created", "action", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    beta_access_code_id: Mapped[int | None] = mapped_column(
        ForeignKey("beta_access_codes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    email_hmac: Mapped[str | None] = mapped_column(String(128), nullable=True)
    code_hmac: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ip_hmac: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
