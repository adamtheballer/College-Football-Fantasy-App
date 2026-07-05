from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base


class AuthRateLimitEvent(Base):
    __tablename__ = "auth_rate_limit_events"
    __table_args__ = (
        Index("ix_auth_rate_limit_events_action_identifier_created", "action", "identifier_hash", "created_at"),
        Index("ix_auth_rate_limit_events_action_ip_created", "action", "ip_hash", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    identifier_hash: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    ip_hash: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
