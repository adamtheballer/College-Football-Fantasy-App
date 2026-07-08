from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.api.deps import get_current_user, get_league_or_404, require_admin_user
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.waiver import (
    WaiverClaimCreate,
    WaiverClaimList,
    WaiverClaimRead,
    WaiverProcessRequest,
    WaiverProcessResult,
)
from collegefootballfantasy_api.app.services.waiver_service import (
    cancel_waiver_claim,
    list_waiver_claims,
    process_waiver_claims,
    submit_waiver_claim,
)

router = APIRouter()


@router.post("/leagues/{league_id}/waivers/claims", response_model=WaiverClaimRead, status_code=201)
def create_waiver_claim_endpoint(
    league_id: int,
    payload: WaiverClaimCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WaiverClaimRead:
    league = get_league_or_404(db, league_id)
    return submit_waiver_claim(db, league=league, payload=payload, current_user=current_user)


@router.get("/leagues/{league_id}/waivers/claims", response_model=WaiverClaimList)
def list_waiver_claims_endpoint(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WaiverClaimList:
    league = get_league_or_404(db, league_id)
    return list_waiver_claims(db, league=league, current_user=current_user)


@router.delete("/waivers/claims/{claim_id}", response_model=WaiverClaimRead)
def cancel_waiver_claim_endpoint(
    claim_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WaiverClaimRead:
    return cancel_waiver_claim(db, claim_id=claim_id, current_user=current_user)


@router.post("/admin/waivers/process", response_model=WaiverProcessResult)
def process_waivers_endpoint(
    payload: WaiverProcessRequest | None = None,
    db: Session = Depends(get_db),
    _admin_user: User = Depends(require_admin_user),
) -> WaiverProcessResult:
    return process_waiver_claims(db, league_id=payload.league_id if payload else None)
