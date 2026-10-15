from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.app_review import AppReviewClaim, AppReviewClaimResult, AppReviewState


def review_state(db: Session, account_id: int) -> AppReviewState:
    claimed_at = db.scalar(select(User.review_request_claimed_at).where(User.id == account_id))
    return AppReviewState(account_id=account_id, enabled=settings.ios_app_review_enabled,
                          review_request_claimed_at=claimed_at)


def claim_review(db: Session, account_id: int, payload: AppReviewClaim) -> AppReviewClaimResult:
    if not settings.ios_app_review_enabled:
        return AppReviewClaimResult(**review_state(db, account_id).model_dump(), authorization="disabled")

    # PostgreSQL serializes competing updates on this immutable user's row and
    # rechecks the NULL predicate after waiting. No read-then-write race and no
    # retry/idempotency key which could replay an earlier grant to another call.
    claimed_at = db.scalar(
        update(User)
        .where(User.id == account_id, User.is_active.is_(True), User.review_request_claimed_at.is_(None))
        .values(review_request_claimed_at=datetime.now(timezone.utc),
                review_request_app_version=payload.app_version, review_request_app_build=payload.app_build)
        .returning(User.review_request_claimed_at)
        .execution_options(synchronize_session=False)
    )
    # Durability precedes returning permission. Losing the response may consume
    # the opportunity; strict at-most-once authorization takes precedence.
    db.commit()
    return AppReviewClaimResult(**review_state(db, account_id).model_dump(),
                                authorization="granted" if claimed_at is not None else "already_claimed")
