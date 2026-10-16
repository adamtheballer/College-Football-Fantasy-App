"""Durable, account-scoped release walkthrough opportunities."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base


class UserReleaseNotice(Base):
    __tablename__ = "user_release_notices"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    release_key: Mapped[str] = mapped_column(String(40), primary_key=True)
    claimed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
