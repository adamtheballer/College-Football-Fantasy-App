from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.models.user_release_notice import UserReleaseNotice
from collegefootballfantasy_api.app.schemas.release_notice import ReleaseNoticeResult

RELEASE_KEY = "1.03"
# Users who joined after this release need the short welcome guide, not a historical recap.
RELEASED_AT = datetime(2026, 10, 19, 2, 49, 40, tzinfo=timezone.utc)


def claim_release_notice(db: Session, account_id: int) -> ReleaseNoticeResult:
    # Serialize across devices on the existing immutable account. The composite
    # primary key independently prevents duplicate account/release receipts.
    user_id = db.scalar(select(User.id).where(User.id == account_id, User.is_active.is_(True)).with_for_update())
    if user_id is None:
        raise HTTPException(401, "active account required")
    row = db.get(UserReleaseNotice, (account_id, RELEASE_KEY))
    created = db.get(User, account_id).created_at
    created = created.replace(tzinfo=timezone.utc) if created.tzinfo is None else created
    granted = row is None and created < RELEASED_AT
    if row is None:
        row = UserReleaseNotice(user_id=account_id, release_key=RELEASE_KEY, claimed_at=datetime.now(timezone.utc))
        db.add(row)
    # Persistence precedes permission, just like native App Review. A lost
    # response can consume an opportunity; retries must never replay a grant.
    db.commit()
    return ReleaseNoticeResult(account_id=account_id, release_key=RELEASE_KEY,
        authorization="granted" if granted else "already_seen", claimed_at=row.claimed_at)
