from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.api.deps import (
    get_current_user,
    get_league_or_404,
    require_commissioner,
    require_league_member,
    require_verified_user,
)
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.league_flow import LeagueWaiversRead
from collegefootballfantasy_api.app.schemas.waiver import (
    WaiverClaimCancel,
    WaiverClaimCreate,
    WaiverClaimRead,
    WaiverProcessResponse,
)
from collegefootballfantasy_api.app.services.league_roster_matchup import build_waivers_view
from collegefootballfantasy_api.app.services.waiver_service import (
    cancel_waiver_claim,
    process_waiver_claims_once,
    submit_waiver_claim,
)

router = APIRouter(prefix="/leagues/{league_id}/waivers")


@router.get("", response_model=LeagueWaiversRead)
def get_league_waiver_tab_endpoint(
    league_id: int,
    limit: int = 50,
    offset: int = 0,
    week: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueWaiversRead:
    league = get_league_or_404(db, league_id)
    require_league_member(db, league.id, current_user)
    return build_waivers_view(
        db,
        league,
        current_user,
        limit=max(1, min(limit, 100)),
        offset=max(0, offset),
        selected_week=week,
    )


@router.post(
    "/claims",
    response_model=WaiverClaimRead,
    status_code=status.HTTP_201_CREATED,
)
def submit_waiver_claim_endpoint(
    league_id: int,
    payload: WaiverClaimCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verified_user),
) -> WaiverClaimRead:
    league = get_league_or_404(db, league_id)
    require_league_member(db, league.id, current_user)
    return submit_waiver_claim(db, league=league, current_user=current_user, payload=payload)


@router.post(
    "/claims/{claim_id}/cancel",
    response_model=WaiverClaimRead,
)
def cancel_waiver_claim_endpoint(
    league_id: int,
    claim_id: int,
    payload: WaiverClaimCancel,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verified_user),
) -> WaiverClaimRead:
    league = get_league_or_404(db, league_id)
    require_league_member(db, league.id, current_user)
    return cancel_waiver_claim(
        db,
        league=league,
        current_user=current_user,
        claim_id=claim_id,
        reason=payload.reason,
    )


@router.post("/process", response_model=WaiverProcessResponse)
def process_waiver_claims_endpoint(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verified_user),
) -> WaiverProcessResponse:
    league, _ = require_commissioner(db, league_id, current_user)
    summary = process_waiver_claims_once(db, league_id=league.id)
    return WaiverProcessResponse(**summary)
