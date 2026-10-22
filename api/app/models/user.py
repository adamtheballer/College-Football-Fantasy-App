from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin
from collegefootballfantasy_api.app.core.name_change import next_name_change_at


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("review_request_invoked_at IS NULL OR review_request_claimed_at IS NOT NULL", name="ck_users_review_invocation_claimed"),
        Index("ix_users_email", "email"),
        Index("ix_users_token", "api_token"),
        CheckConstraint(
            "(review_request_claimed_at IS NULL AND review_request_app_version IS NULL AND review_request_app_build IS NULL) OR "
            "(review_request_claimed_at IS NOT NULL AND review_request_app_version IS NOT NULL AND review_request_app_build IS NOT NULL)",
            name="ck_users_review_request_metadata",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True)
    username: Mapped[str | None] = mapped_column(String(80), unique=True, index=True, nullable=True)
    first_name: Mapped[str] = mapped_column(String(100))
    # An avatar can be either a vetted public HTTPS URL or a compact JPEG data
    # URL created by the mobile photo picker. Text avoids truncating the latter.
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    api_token: Mapped[str] = mapped_column(String(100), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    beta_access_granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_test_account: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    review_request_invoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_failed_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    manager_name_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    auth_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    # Authorization consumption, never evidence of a displayed/submitted review.
    review_request_claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_request_app_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    review_request_app_build: Mapped[str | None] = mapped_column(String(80), nullable=True)

    @property
    def early_access_pro_eligible(self) -> bool:
        """Existing code-redemption ledger, redeemable for one Pro year at alpha launch."""
        return self.beta_access_granted_at is not None

    @property
    def manager_name_change_available_at(self) -> datetime | None:
        """Return the next self-service manager-name change time, if limited."""
        return next_name_change_at(self.manager_name_changed_at)
