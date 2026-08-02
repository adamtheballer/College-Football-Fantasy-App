from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.beta_access import (
    BetaAccessValidationRequest,
    BetaAccessValidationResponse,
)
from collegefootballfantasy_api.app.services.beta_access import validate_and_reserve_beta_access

router = APIRouter()


@router.post("/validate", response_model=BetaAccessValidationResponse)
def validate_beta_access(
    payload: BetaAccessValidationRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> BetaAccessValidationResponse:
    reservation_token, expires_at, email = validate_and_reserve_beta_access(
        db,
        email_input=payload.email,
        code_input=payload.code,
        request=request,
    )
    return BetaAccessValidationResponse(
        reservation_token=reservation_token,
        reservation_expires_at=expires_at,
        email=email,
        # This is returned only after the exact e-mail/code pair validates, so
        # arbitrary e-mail addresses cannot be used to enumerate accounts.
        existing_account=db.query(User).filter(User.email == email).first() is not None,
    )
