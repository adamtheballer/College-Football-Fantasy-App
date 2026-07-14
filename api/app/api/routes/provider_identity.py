from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.api.deps import require_admin_user
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.provider_identity import ProviderIdentityAudit, UnmatchedProviderRow
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.provider_identity import (
    ProviderIdentityAuditRead,
    ProviderReadinessRead,
    ProviderRowMappingRequest,
    ProviderRowStatusRequest,
    UnmatchedProviderRowRead,
    UnmatchedProviderRowsList,
    UnmatchedStatus,
)
from collegefootballfantasy_api.app.services.provider_identity import (
    ProviderIdentityConflict,
    map_unmatched_row_to_player,
    mark_unmatched_row_status,
    provider_identity_readiness,
)

router = APIRouter()


@router.get("/unmatched", response_model=UnmatchedProviderRowsList)
def list_unmatched_provider_rows(
    status_filter: UnmatchedStatus | None = Query(default=None, alias="status"),
    provider: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
) -> UnmatchedProviderRowsList:
    query = select(UnmatchedProviderRow)
    count_query = select(func.count(UnmatchedProviderRow.id))
    if status_filter:
        query = query.where(UnmatchedProviderRow.status == status_filter)
        count_query = count_query.where(UnmatchedProviderRow.status == status_filter)
    if provider:
        normalized_provider = provider.strip().lower()
        query = query.where(UnmatchedProviderRow.provider == normalized_provider)
        count_query = count_query.where(UnmatchedProviderRow.provider == normalized_provider)
    rows = (
        db.execute(query.order_by(UnmatchedProviderRow.updated_at.desc()).limit(limit).offset(offset))
        .scalars()
        .all()
    )
    total = db.scalar(count_query) or 0
    return UnmatchedProviderRowsList(
        data=[UnmatchedProviderRowRead.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/unmatched/{row_id}/map", response_model=UnmatchedProviderRowRead)
def map_unmatched_provider_row(
    row_id: int,
    payload: ProviderRowMappingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
) -> UnmatchedProviderRowRead:
    try:
        row = map_unmatched_row_to_player(
            db,
            unmatched_row_id=row_id,
            player_id=payload.player_id,
            actor_user_id=current_user.id,
            match_confidence=payload.match_confidence,
            reason=payload.reason,
        )
        db.commit()
        db.refresh(row)
        return UnmatchedProviderRowRead.model_validate(row)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ProviderIdentityConflict, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/unmatched/{row_id}/ignore", response_model=UnmatchedProviderRowRead)
def ignore_unmatched_provider_row(
    row_id: int,
    payload: ProviderRowStatusRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
) -> UnmatchedProviderRowRead:
    try:
        row = mark_unmatched_row_status(
            db,
            unmatched_row_id=row_id,
            status="ignored",
            actor_user_id=current_user.id,
            reason=payload.reason if payload else None,
        )
        db.commit()
        db.refresh(row)
        return UnmatchedProviderRowRead.model_validate(row)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/unmatched/{row_id}/resolve", response_model=UnmatchedProviderRowRead)
def resolve_unmatched_provider_row(
    row_id: int,
    payload: ProviderRowStatusRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
) -> UnmatchedProviderRowRead:
    try:
        row = mark_unmatched_row_status(
            db,
            unmatched_row_id=row_id,
            status="resolved",
            actor_user_id=current_user.id,
            reason=payload.reason if payload else None,
        )
        db.commit()
        db.refresh(row)
        return UnmatchedProviderRowRead.model_validate(row)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/unmatched/{row_id}/reopen", response_model=UnmatchedProviderRowRead)
def reopen_unmatched_provider_row(
    row_id: int,
    payload: ProviderRowStatusRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
) -> UnmatchedProviderRowRead:
    try:
        row = mark_unmatched_row_status(
            db,
            unmatched_row_id=row_id,
            status="open",
            actor_user_id=current_user.id,
            reason=payload.reason if payload else None,
        )
        db.commit()
        db.refresh(row)
        return UnmatchedProviderRowRead.model_validate(row)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/readiness", response_model=ProviderReadinessRead)
def get_provider_identity_readiness(
    provider: str = Query(default="espn"),
    season: int = Query(..., ge=2000, le=2100),
    week: int = Query(..., ge=1, le=20),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
) -> ProviderReadinessRead:
    return ProviderReadinessRead.model_validate(
        provider_identity_readiness(db, provider=provider, season=season, week=week)
    )


@router.get("/audits", response_model=list[ProviderIdentityAuditRead])
def list_provider_identity_audits(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_user),
) -> list[ProviderIdentityAuditRead]:
    rows = (
        db.execute(select(ProviderIdentityAudit).order_by(ProviderIdentityAudit.created_at.desc()).limit(limit).offset(offset))
        .scalars()
        .all()
    )
    return [ProviderIdentityAuditRead.model_validate(row) for row in rows]
