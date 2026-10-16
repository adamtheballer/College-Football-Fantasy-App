from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.api.deps import require_verified_user
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.release_notice import ReleaseNoticeClaim, ReleaseNoticeResult
from collegefootballfantasy_api.app.services.release_notice import claim_release_notice

router = APIRouter()


@router.post("/1.03/claim", response_model=ReleaseNoticeResult)
def claim(payload: ReleaseNoticeClaim, request: Request, db: Session = Depends(get_db),
          user: User = Depends(require_verified_user)) -> ReleaseNoticeResult:
    # Precondition only: ownership always comes from the verified JWT.
    if request.headers.get("x-cffb-release-account") != str(user.id):
        raise HTTPException(409, "release notice account changed")
    return claim_release_notice(db, user.id)
