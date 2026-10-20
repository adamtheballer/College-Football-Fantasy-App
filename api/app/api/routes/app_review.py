from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.api.deps import require_verified_user
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.app_review import AppReviewClaim, AppReviewClaimResult, AppReviewState
from collegefootballfantasy_api.app.services.app_review import claim_review, review_state

router = APIRouter()


def native_ios_request(request: Request) -> None:
    # Origin is fixed by the bundled WKWebView. A normal browser cannot opt in
    # with just a custom header. This is platform gating, not device attestation.
    if request.headers.get("origin") != "capacitor://localhost" or request.headers.get("x-cffb-native-session") != "ios":
        raise HTTPException(status_code=403, detail="native iOS session required")


def review_account(request: Request, current_user: User = Depends(require_verified_user)) -> User:
    # A precondition, NOT an account selector. The verified JWT always supplies
    # the target; this prevents a refreshed/switched session consuming the next
    # account's opportunity while an old UI callback is settling.
    if request.headers.get("x-cffb-review-account") != str(current_user.id):
        raise HTTPException(status_code=409, detail="review account changed")
    return current_user


@router.get("/state", response_model=AppReviewState, dependencies=[Depends(native_ios_request)])
def state(current_user: User = Depends(review_account), db: Session = Depends(get_db)) -> AppReviewState:
    return review_state(db, current_user.id)


@router.post("/claim", response_model=AppReviewClaimResult, dependencies=[Depends(native_ios_request)])
def claim(payload: AppReviewClaim, current_user: User = Depends(review_account),
          db: Session = Depends(get_db)) -> AppReviewClaimResult:
    return claim_review(db, current_user.id, payload)


@router.post("/invoked", response_model=AppReviewState, dependencies=[Depends(native_ios_request)])
def invoked(current_user: User = Depends(review_account), db: Session = Depends(get_db)):
    from datetime import datetime, timezone
    from sqlalchemy import update
    db.execute(update(User).where(User.id == current_user.id, User.review_request_claimed_at.is_not(None),
        User.review_request_invoked_at.is_(None)).values(review_request_invoked_at=datetime.now(timezone.utc)))
    db.commit()
    return review_state(db, current_user.id)
