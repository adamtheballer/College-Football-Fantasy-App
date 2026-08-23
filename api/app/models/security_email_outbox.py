from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class SecurityEmailOutbox(TimestampMixin, Base):
    """Durable, token-free work items for account-security email delivery."""

    __tablename__ = "security_email_outbox"
    __table_args__ = (
        Index("ix_security_email_outbox_status_due", "status", "next_attempt_at"),
        Index("ix_security_email_outbox_user_id", "user_id"),
        Index("ix_security_email_outbox_token_id", "auth_action_token_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    auth_action_token_id: Mapped[int | None] = mapped_column(ForeignKey("auth_action_tokens.id", ondelete="CASCADE"), nullable=True)
    message_type: Mapped[str] = mapped_column(String(60), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
