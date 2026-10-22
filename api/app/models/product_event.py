"""Bounded first-party diagnostics. No free-form properties, IPs or email addresses."""
from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column
from collegefootballfantasy_api.app.models import Base


class ProductEvent(Base):
    __tablename__ = 'product_events'
    __table_args__ = (CheckConstraint("kind IN ('session','challenge_view','challenge_start','challenge_submit','challenge_share','guide_complete','notification_open')", name='ck_product_events_kind'), CheckConstraint("platform IN ('web','ios','android')", name='ck_product_events_platform'), Index('ix_product_events_at_kind', 'at', 'kind'), Index('ix_product_events_user_at', 'user_id', 'at'))
    id: Mapped[int] = mapped_column(primary_key=True)
    dedupe_key: Mapped[str] = mapped_column(String(180), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    kind: Mapped[str] = mapped_column(String(32))
    challenge_id: Mapped[int | None] = mapped_column(ForeignKey('weekly_challenges.id', ondelete='CASCADE'))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    platform: Mapped[str] = mapped_column(String(12), default='web')
    app_version: Mapped[str | None] = mapped_column(String(40))
    app_build: Mapped[str | None] = mapped_column(String(40))
