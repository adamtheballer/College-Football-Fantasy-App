from typing import Literal

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
    FreeAgentAdd,
    FreeAgentAddRead,
    WaiverClaimCancel,
    WaiverClaimCreate,
    WaiverClaimReorder,
    WaiverClaimRead,
    WaiverProcessResponse,
)
from collegefootballfantasy_api.app.services.league_roster_matchup import build_waivers_view
from collegefootballfantasy_api.app.services.waiver_service import (
    add_free_agent,
    cancel_waiver_claim,
    edit_waiver_claim,
    process_waiver_claims_once,
    reorder_waiver_claims,
    submit_waiver_claim,
)
from collegefootballfantasy_api.app.services.content_moderation import moderate_user_text

router = APIRouter(prefix="/leagues/{league_id}/waivers")


@router.get("", response_model=LeagueWaiversRead)
def get_league_waiver_tab_endpoint(
    league_id: int,
    limit: int = 50,
    offset: int = 0,
    week: int | None = None,
    scope: Literal["waiver", "all"] = "waiver",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueWaiversRead:
    league = get_league_or_404(db, league_id)
    require_league_member(db, league.id, current_user)
    return build_waivers_view(
        db,
        league,
        current_user,
        # Both the waiver pool and all-player research view are intentionally
        # bounded high enough for the current canonical universe. Truncating
        # them at a single 50/100-player page hides valid player targets.
        limit=max(1, min(limit, 1000)),
        offset=max(0, offset),
        selected_week=week,
        scope=scope,
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
    payload.reason = moderate_user_text(
        db, actor_user_id=current_user.id, league_id=league.id, field_name="waiver_note", value=payload.reason
    )
    return submit_waiver_claim(db, league=league, current_user=current_user, payload=payload)


@router.post(
    "/free-agents/{player_id}/add",
    response_model=FreeAgentAddRead,
    status_code=status.HTTP_201_CREATED,
)
def add_free_agent_endpoint(
    league_id: int,
    player_id: int,
    payload: FreeAgentAdd,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verified_user),
) -> FreeAgentAddRead:
    league = get_league_or_404(db, league_id)
    require_league_member(db, league.id, current_user)
    return add_free_agent(
        db,
        league=league,
        current_user=current_user,
        player_id=player_id,
        payload=payload,
    )


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
    payload.reason = moderate_user_text(
        db, actor_user_id=current_user.id, league_id=league.id, field_name="waiver_note", value=payload.reason
    )
    return cancel_waiver_claim(
        db,
        league=league,
        current_user=current_user,
        claim_id=claim_id,
        reason=payload.reason,
    )


@router.patch("/claims/{claim_id}", response_model=WaiverClaimRead)
def edit_waiver_claim_endpoint(
    league_id: int,
    claim_id: int,
    payload: WaiverClaimCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verified_user),
) -> WaiverClaimRead:
    league = get_league_or_404(db, league_id)
    require_league_member(db, league.id, current_user)
    payload.reason = moderate_user_text(
        db, actor_user_id=current_user.id, league_id=league.id, field_name="waiver_note", value=payload.reason
    )
    return edit_waiver_claim(db, league=league, current_user=current_user, claim_id=claim_id, payload=payload)


@router.post("/claims/reorder", response_model=list[WaiverClaimRead])
def reorder_waiver_claims_endpoint(
    league_id: int,
    payload: WaiverClaimReorder,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verified_user),
) -> list[WaiverClaimRead]:
    league = get_league_or_404(db, league_id)
    require_league_member(db, league.id, current_user)
    return reorder_waiver_claims(db, league=league, current_user=current_user, claim_ids=payload.claim_ids)


@router.post("/process", response_model=WaiverProcessResponse)
def process_waiver_claims_endpoint(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verified_user),
) -> WaiverProcessResponse:
    league, _ = require_commissioner(db, league_id, current_user)
    summary = process_waiver_claims_once(db, league_id=league.id)
    return WaiverProcessResponse(**summary)
