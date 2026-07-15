from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.api.deps import require_admin_user
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.scoring_admin_audit import ScoringAdminAudit
from collegefootballfantasy_api.app.models.scoring_run import ScoringRun
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.models.worker_heartbeat import WorkerHeartbeat
from collegefootballfantasy_api.app.schemas.admin_scoring import (
    AdminActionResponse,
    AdminCorrectionRequest,
    AdminReconcileLeagueWeekRequest,
    AdminReconcilePlayerWeekRequest,
    AdminRerunScoringRequest,
    AdminScoringAuditRead,
    AdminWeekStatusRequest,
    CorrectionPreviewResponse,
    ProviderHealthResponse,
    ScoringRunRead,
    ScoringRunsList,
)
from collegefootballfantasy_api.app.services.admin_scoring_service import (
    apply_stat_correction,
    provider_health,
    preview_stat_correction,
    reconcile_league_week,
    reconcile_player_week,
    rerun_scoring,
    set_week_status,
)

router = APIRouter()


@router.get("/workers")
def list_worker_health(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
) -> list[dict]:
    rows = db.query(WorkerHeartbeat).order_by(WorkerHeartbeat.worker_name.asc()).all()
    return [
        {
            "worker_name": row.worker_name,
            "status": row.status,
            "heartbeat_at": row.heartbeat_at,
            "last_success_at": row.last_success_at,
            "last_failure_at": row.last_failure_at,
            "details": row.details_json,
        }
        for row in rows
    ]


@router.get("/runs", response_model=ScoringRunsList)
def list_scoring_runs(
    status_filter: str | None = Query(default=None, alias="status"),
    league_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
) -> ScoringRunsList:
    query = db.query(ScoringRun)
    count_query = db.query(func.count(ScoringRun.id))
    if status_filter:
        query = query.filter(ScoringRun.status == status_filter)
        count_query = count_query.filter(ScoringRun.status == status_filter)
    if league_id is not None:
        query = query.filter(ScoringRun.league_id == league_id)
        count_query = count_query.filter(ScoringRun.league_id == league_id)
    rows = query.order_by(ScoringRun.started_at.desc(), ScoringRun.id.desc()).offset(offset).limit(limit).all()
    return ScoringRunsList(
        data=[ScoringRunRead.model_validate(row) for row in rows],
        total=count_query.scalar() or 0,
        limit=limit,
        offset=offset,
    )


@router.get("/provider-health", response_model=ProviderHealthResponse)
def get_provider_health(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
) -> ProviderHealthResponse:
    return provider_health(db)


@router.post("/rerun", response_model=AdminActionResponse)
def rerun_scoring_endpoint(
    payload: AdminRerunScoringRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
) -> AdminActionResponse:
    try:
        return rerun_scoring(db, payload, current_user)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/corrections/preview", response_model=CorrectionPreviewResponse)
def preview_correction_endpoint(
    payload: AdminCorrectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
) -> CorrectionPreviewResponse:
    try:
        return preview_stat_correction(db, payload)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/corrections/apply", response_model=AdminActionResponse)
def apply_correction_endpoint(
    payload: AdminCorrectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
) -> AdminActionResponse:
    try:
        return apply_stat_correction(db, payload, current_user)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/corrections", response_model=list[AdminScoringAuditRead])
def list_correction_history(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
) -> list[AdminScoringAuditRead]:
    rows = (
        db.query(ScoringAdminAudit)
        .filter(ScoringAdminAudit.action == "apply_stat_correction")
        .order_by(ScoringAdminAudit.created_at.desc(), ScoringAdminAudit.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [AdminScoringAuditRead.model_validate(row) for row in rows]


@router.post("/reconcile/player-week", response_model=AdminActionResponse)
def reconcile_player_week_endpoint(
    payload: AdminReconcilePlayerWeekRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
) -> AdminActionResponse:
    try:
        return reconcile_player_week(
            db,
            player_id=payload.player_id,
            season=payload.season,
            week=payload.week,
            reason=payload.reason,
            actor=current_user,
            league_id=payload.league_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/reconcile/league-week", response_model=AdminActionResponse)
def reconcile_league_week_endpoint(
    payload: AdminReconcileLeagueWeekRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
) -> AdminActionResponse:
    try:
        return reconcile_league_week(
            db,
            league_id=payload.league_id,
            season=payload.season,
            week=payload.week,
            reason=payload.reason,
            actor=current_user,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/weeks/finalize", response_model=AdminActionResponse)
def finalize_week_endpoint(
    payload: AdminWeekStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
) -> AdminActionResponse:
    try:
        return set_week_status(
            db,
            league_id=payload.league_id,
            season=payload.season,
            week=payload.week,
            status="final",
            reason=payload.reason,
            actor=current_user,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/weeks/reopen", response_model=AdminActionResponse)
def reopen_week_endpoint(
    payload: AdminWeekStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
) -> AdminActionResponse:
    try:
        return set_week_status(
            db,
            league_id=payload.league_id,
            season=payload.season,
            week=payload.week,
            status="live",
            reason=payload.reason,
            actor=current_user,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
