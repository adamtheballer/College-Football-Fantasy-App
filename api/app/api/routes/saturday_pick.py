from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.api.deps import (
    get_current_user,
    require_admin_user,
)
from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.saturday_pick import SaturdayPickContest
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.saturday_pick import (
    SaturdayPickContestCreate,
    SaturdayPickContestPrepare,
    SaturdayPickContestRead,
    SaturdayPickContestPublish,
    SaturdayPickContestReviewUpdate,
    SaturdayPickAdminReviewRead,
    SaturdayPickEntryRead,
    SaturdayPickEntryWrite,
    SaturdayPickRotationRead,
)
from collegefootballfantasy_api.app.services.saturday_pick_service import (
    DEFAULT_ROTATION,
    contest_read,
    create_contest,
    finalize_contest,
    list_review_candidates,
    publish_contest,
    record_content_audit,
    refresh_contest_live_scores,
    recommended_position,
    replace_draft_contest,
    review_snapshot,
    save_entry,
)
from collegefootballfantasy_api.app.services.content_moderation import moderate_user_text, moderate_user_url


router = APIRouter()
admin_router = APIRouter()
PUBLIC_CONTEST_STATUSES = ("SCHEDULED", "OPEN", "LOCKED", "SCORING", "PROVISIONAL", "FINAL")


def _require_public_enabled() -> None:
    if not settings.saturday_pick_6_enabled or not settings.saturday_pick_6_public_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saturday Pick 6 is not available.")


def _contest_or_404(db: Session, contest_id: int) -> SaturdayPickContest:
    contest = db.get(SaturdayPickContest, contest_id)
    if not contest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saturday Pick 6 contest not found")
    return contest


@router.get("/current", response_model=SaturdayPickContestRead)
def get_current_contest(
    season: int | None = Query(None, ge=2000, le=2100),
    week: int | None = Query(None, ge=1, le=30),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SaturdayPickContestRead:
    _require_public_enabled()
    statuses = PUBLIC_CONTEST_STATUSES if season is not None or week is not None else (
        "OPEN", "LOCKED", "SCORING", "PROVISIONAL", "FINAL"
    )
    query = db.query(SaturdayPickContest).filter(SaturdayPickContest.status.in_(statuses))
    if season is not None:
        query = query.filter(SaturdayPickContest.season == season)
    if week is not None:
        query = query.filter(SaturdayPickContest.week_number == week)
    contest = query.order_by(SaturdayPickContest.season.desc(), SaturdayPickContest.week_number.desc()).first()
    if not contest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active Saturday Pick 6 contest")
    return contest_read(db, contest, current_user)


@router.get("/active", response_model=SaturdayPickContestRead)
def get_active_contest(
    season: int | None = Query(None, ge=2000, le=2100),
    week: int | None = Query(None, ge=1, le=30),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SaturdayPickContestRead:
    """Compatibility alias for the public active-contest contract."""

    return get_current_contest(season=season, week=week, db=db, current_user=current_user)


@router.get("/{contest_id}", response_model=SaturdayPickContestRead)
def get_contest(
    contest_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SaturdayPickContestRead:
    _require_public_enabled()
    return contest_read(db, _contest_or_404(db, contest_id), current_user)


@router.get("/{contest_id}/results", response_model=SaturdayPickContestRead)
def get_results(
    contest_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SaturdayPickContestRead:
    _require_public_enabled()
    return contest_read(db, _contest_or_404(db, contest_id), current_user)


@router.put("/{contest_id}/entry", response_model=SaturdayPickEntryRead)
def submit_entry(
    contest_id: int,
    payload: SaturdayPickEntryWrite,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SaturdayPickEntryRead:
    _require_public_enabled()
    try:
        entry = save_entry(db, _contest_or_404(db, contest_id), current_user, payload.selected_pick_player_id)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return SaturdayPickEntryRead(
        id=entry.id,
        selected_pick_player_id=entry.selected_pick_player_id,
        submitted_at=entry.submitted_at,
        is_winner=entry.is_winner,
        reward_unlocked_at=entry.reward_unlocked_at,
    )


@admin_router.get("/rotation", response_model=SaturdayPickRotationRead)
def get_rotation(
    week: int = Query(..., ge=1, le=30),
    current_user: User = Depends(require_admin_user),
) -> SaturdayPickRotationRead:
    del current_user
    return SaturdayPickRotationRead(default_rotation=list(DEFAULT_ROTATION), recommended_position=recommended_position(week))


@admin_router.post("", response_model=SaturdayPickContestRead, status_code=status.HTTP_201_CREATED)
def create_contest_endpoint(
    payload: SaturdayPickContestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
) -> SaturdayPickContestRead:
    payload.title = moderate_user_text(
        db, actor_user_id=current_user.id, field_name="saturday_pick_title", value=payload.title, required=True
    ) or ""
    payload.sponsor_name = moderate_user_text(
        db, actor_user_id=current_user.id, field_name="saturday_pick_sponsor_name", value=payload.sponsor_name
    )
    payload.sponsor_offer_text = moderate_user_text(
        db, actor_user_id=current_user.id, field_name="saturday_pick_sponsor_offer", value=payload.sponsor_offer_text
    )
    payload.sponsor_terms = moderate_user_text(
        db, actor_user_id=current_user.id, field_name="saturday_pick_sponsor_terms", value=payload.sponsor_terms
    )
    payload.override_reason = moderate_user_text(
        db, actor_user_id=current_user.id, field_name="saturday_pick_override_reason", value=payload.override_reason
    )
    payload.sponsor_logo_url = moderate_user_url(
        db, actor_user_id=current_user.id, field_name="saturday_pick_sponsor_logo_url", value=payload.sponsor_logo_url
    )
    payload.sponsor_url = moderate_user_url(
        db, actor_user_id=current_user.id, field_name="saturday_pick_sponsor_url", value=payload.sponsor_url
    )
    try:
        contest = create_contest(db, payload, current_user)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return contest_read(db, contest, current_user)


@admin_router.get("/review", response_model=SaturdayPickAdminReviewRead)
def get_review(
    season: int = Query(default_factory=lambda: datetime.now().year, ge=2000, le=2100),
    week: int = Query(1, ge=1, le=30),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
) -> SaturdayPickAdminReviewRead:
    return review_snapshot(db, season=season, week=week, viewer=current_user)


@admin_router.post("/prepare", response_model=SaturdayPickAdminReviewRead, status_code=status.HTTP_201_CREATED)
def prepare_review(
    payload: SaturdayPickContestPrepare,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
) -> SaturdayPickAdminReviewRead:
    existing = (
        db.query(SaturdayPickContest)
        .filter(SaturdayPickContest.season == payload.season, SaturdayPickContest.week_number == payload.week_number)
        .one_or_none()
    )
    if existing:
        return review_snapshot(db, season=payload.season, week=payload.week_number, viewer=current_user)
    position = recommended_position(payload.week_number)
    candidates = list_review_candidates(db, season=payload.season, week=payload.week_number, position=position)
    if len(candidates) < 6:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Six eligible players with verified projections are required before preparation.")
    try:
        contest = create_contest(
            db,
            SaturdayPickContestCreate(
                season=payload.season,
                week_number=payload.week_number,
                contest_position=position,
                featured_player_ids=[candidate.player_id for candidate in candidates[:6]],
                title="Saturday Pick 6",
            ),
            current_user,
        )
        record_content_audit(
            db, contest=contest, actor=current_user, season=payload.season, week=payload.week_number,
            action="prepared", reason=payload.reason, details={"position": position},
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return review_snapshot(db, season=payload.season, week=payload.week_number, viewer=current_user)


@admin_router.put("/{contest_id}/review", response_model=SaturdayPickAdminReviewRead)
def save_review(
    contest_id: int,
    payload: SaturdayPickContestReviewUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
) -> SaturdayPickAdminReviewRead:
    contest = _contest_or_404(db, contest_id)
    title = moderate_user_text(db, actor_user_id=current_user.id, field_name="saturday_pick_title", value=payload.title, required=True) or ""
    reason = moderate_user_text(db, actor_user_id=current_user.id, field_name="saturday_pick_review_reason", value=payload.reason, required=True)
    sponsor_name = moderate_user_text(db, actor_user_id=current_user.id, field_name="saturday_pick_sponsor_name", value=payload.sponsor_name)
    sponsor_offer = moderate_user_text(db, actor_user_id=current_user.id, field_name="saturday_pick_sponsor_offer", value=payload.sponsor_offer_text)
    sponsor_terms = moderate_user_text(db, actor_user_id=current_user.id, field_name="saturday_pick_sponsor_terms", value=payload.sponsor_terms)
    sponsor_logo = moderate_user_url(db, actor_user_id=current_user.id, field_name="saturday_pick_sponsor_logo_url", value=payload.sponsor_logo_url)
    sponsor_url = moderate_user_url(db, actor_user_id=current_user.id, field_name="saturday_pick_sponsor_url", value=payload.sponsor_url)
    try:
        replace_draft_contest(
            db,
            contest=contest,
            payload=SaturdayPickContestCreate(
                season=contest.season, week_number=contest.week_number, contest_position=contest.contest_position,
                featured_player_ids=payload.featured_player_ids, title=title, sponsor_name=sponsor_name,
                sponsor_logo_url=sponsor_logo, sponsor_offer_text=sponsor_offer, sponsor_code=payload.sponsor_code,
                sponsor_url=sponsor_url, sponsor_terms=sponsor_terms,
            ),
        )
        record_content_audit(
            db, contest=contest, actor=current_user, season=contest.season, week=contest.week_number,
            action="review_saved", reason=reason, details={"featured_player_ids": payload.featured_player_ids},
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return review_snapshot(db, season=contest.season, week=contest.week_number, viewer=current_user)


@admin_router.post("/{contest_id}/publish", response_model=SaturdayPickContestRead)
def publish_contest_endpoint(
    contest_id: int,
    payload: SaturdayPickContestPublish,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
) -> SaturdayPickContestRead:
    contest = _contest_or_404(db, contest_id)
    if payload.lock_at is not None:
        contest.lock_at = payload.lock_at
    try:
        publish_contest(db, contest)
        record_content_audit(
            db, contest=contest, actor=current_user, season=contest.season, week=contest.week_number,
            action="published", reason=payload.reason,
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return contest_read(db, contest, current_user)


@admin_router.post("/{contest_id}/finalize", response_model=SaturdayPickContestRead)
def finalize_contest_endpoint(
    contest_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
) -> SaturdayPickContestRead:
    try:
        contest = finalize_contest(db, _contest_or_404(db, contest_id))
        record_content_audit(
            db, contest=contest, actor=current_user, season=contest.season, week=contest.week_number,
            action="finalized", reason=None,
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return contest_read(db, contest, current_user)


@admin_router.post("/{contest_id}/refresh", response_model=SaturdayPickContestRead)
def refresh_contest_endpoint(
    contest_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
) -> SaturdayPickContestRead:
    contest = _contest_or_404(db, contest_id)
    refresh_contest_live_scores(db, contest)
    db.commit()
    return contest_read(db, contest, current_user)
