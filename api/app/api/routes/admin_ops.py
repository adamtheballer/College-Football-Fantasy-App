from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.api.deps import require_admin_user
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.audit_event import AuditEvent
from collegefootballfantasy_api.app.models.auth_rate_limit_event import AuthRateLimitEvent
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_member import LeagueMember
from collegefootballfantasy_api.app.models.provider_sync_job import ProviderSyncJob
from collegefootballfantasy_api.app.models.provider_sync_state import ProviderSyncState
from collegefootballfantasy_api.app.models.refresh_session import RefreshSession
from collegefootballfantasy_api.app.models.scoring_run import ScoringRun
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.trade_offer import TradeOffer
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.models.waiver_claim import WaiverClaim
from collegefootballfantasy_api.app.services.operations_metrics import operations_metrics_snapshot
from collegefootballfantasy_api.app.services.readiness import check_alembic_readiness

router = APIRouter()


def _dt(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _failed_scoring_run(row: ScoringRun) -> dict:
    return {
        "id": row.id,
        "league_id": row.league_id,
        "season": row.season,
        "week": row.week,
        "provider": row.provider,
        "status": row.status,
        "started_at": row.started_at,
        "completed_at": row.completed_at,
        "error_message": row.error_message,
        "rows_fetched": row.rows_fetched,
        "rows_matched": row.rows_matched,
        "rows_unmatched": row.rows_unmatched,
        "retry_count": row.retry_count,
    }


def _provider_job(row: ProviderSyncJob) -> dict:
    return {
        "id": row.id,
        "provider": row.provider,
        "feed": row.feed,
        "season": row.season,
        "week": row.week,
        "scope": row.scope,
        "status": row.status,
        "started_at": row.started_at,
        "finished_at": row.finished_at,
        "rows_seen": row.rows_seen,
        "rows_inserted": row.rows_inserted,
        "rows_updated": row.rows_updated,
        "rows_rejected": row.rows_rejected,
        "error_summary": row.error_summary,
    }


def _audit_event(row: AuditEvent) -> dict:
    return {
        "id": row.id,
        "actor_user_id": row.actor_user_id,
        "league_id": row.league_id,
        "team_id": row.team_id,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "action": row.action,
        "before_json": row.before_json,
        "after_json": row.after_json,
        "request_id": row.request_id,
        "created_at": row.created_at,
    }


def _is_stale(expires_at: datetime | None) -> bool:
    if expires_at is None:
        return True
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= datetime.now(timezone.utc)


@router.get("/metrics")
def operations_metrics(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin_user),
) -> dict:
    readiness = check_alembic_readiness(db).as_dict()
    failed_scoring_runs = (
        db.query(ScoringRun)
        .filter(ScoringRun.status.in_(("failed", "partial")))
        .order_by(ScoringRun.started_at.desc(), ScoringRun.id.desc())
        .limit(10)
        .all()
    )
    failed_provider_jobs = (
        db.query(ProviderSyncJob)
        .filter(ProviderSyncJob.status.in_(("failed", "partial")))
        .order_by(ProviderSyncJob.started_at.desc(), ProviderSyncJob.id.desc())
        .limit(10)
        .all()
    )
    provider_states = db.query(ProviderSyncState).all()
    pending_waivers = db.query(func.count(WaiverClaim.id)).filter(WaiverClaim.status == "pending").scalar() or 0
    open_trades = (
        db.query(func.count(TradeOffer.id))
        .filter(TradeOffer.status.in_(("proposed", "accepted", "commissioner_review")))
        .scalar()
        or 0
    )
    recent_audit_events = db.query(func.count(AuditEvent.id)).scalar() or 0
    return {
        "readiness": readiness,
        "process": operations_metrics_snapshot(),
        "jobs": {
            "failed_scoring_runs": [_failed_scoring_run(row) for row in failed_scoring_runs],
            "failed_provider_jobs": [_provider_job(row) for row in failed_provider_jobs],
            "stale_provider_states": [
                {
                    "id": row.id,
                    "provider": row.provider,
                    "feed": row.feed,
                    "scope_key": row.scope_key,
                    "status": row.status,
                    "last_successful_sync_at": row.last_success_at,
                    "cache_expires_at": row.expires_at,
                    "error_message": row.error_message,
                    "consecutive_failures": row.consecutive_failures,
                }
                for row in provider_states
                if _is_stale(row.expires_at) or row.status != "success"
            ],
            "pending_waiver_claims": int(pending_waivers),
            "open_trade_offers": int(open_trades),
            "audit_event_count": int(recent_audit_events),
        },
    }


@router.get("/failed-jobs")
def failed_jobs(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin_user),
) -> dict:
    scoring_runs = (
        db.query(ScoringRun)
        .filter(ScoringRun.status.in_(("failed", "partial")))
        .order_by(ScoringRun.started_at.desc(), ScoringRun.id.desc())
        .limit(limit)
        .all()
    )
    provider_jobs = (
        db.query(ProviderSyncJob)
        .filter(ProviderSyncJob.status.in_(("failed", "partial")))
        .order_by(ProviderSyncJob.started_at.desc(), ProviderSyncJob.id.desc())
        .limit(limit)
        .all()
    )
    return {
        "scoring_runs": [_failed_scoring_run(row) for row in scoring_runs],
        "provider_sync_jobs": [_provider_job(row) for row in provider_jobs],
    }


@router.get("/audit-events")
def audit_events(
    league_id: int | None = None,
    actor_user_id: int | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    request_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin_user),
) -> dict:
    query = db.query(AuditEvent)
    if league_id is not None:
        query = query.filter(AuditEvent.league_id == league_id)
    if actor_user_id is not None:
        query = query.filter(AuditEvent.actor_user_id == actor_user_id)
    if action:
        query = query.filter(AuditEvent.action == action)
    if entity_type:
        query = query.filter(AuditEvent.entity_type == entity_type)
    if request_id:
        query = query.filter(AuditEvent.request_id == request_id)
    rows = query.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).limit(limit).all()
    return {"data": [_audit_event(row) for row in rows]}


@router.get("/users/{user_id}/security")
def user_security(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin_user),
) -> dict:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    sessions = (
        db.query(RefreshSession)
        .filter(RefreshSession.user_id == user_id)
        .order_by(RefreshSession.issued_at.desc(), RefreshSession.id.desc())
        .limit(50)
        .all()
    )
    auth_events = (
        db.query(AuthRateLimitEvent)
        .order_by(AuthRateLimitEvent.created_at.desc(), AuthRateLimitEvent.id.desc())
        .limit(100)
        .all()
    )
    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "is_active": user.is_active,
            "email_verified_at": user.email_verified_at,
            "last_login": user.last_login,
            "failed_login_attempts": user.failed_login_attempts,
            "locked_until": user.locked_until,
            "password_changed_at": user.password_changed_at,
        },
        "sessions": [
            {
                "id": row.id,
                "issued_at": row.issued_at,
                "expires_at": row.expires_at,
                "revoked_at": row.revoked_at,
                "last_used_at": row.last_used_at,
                "user_agent": row.user_agent,
                "ip_address": row.ip_address,
            }
            for row in sessions
        ],
        "recent_auth_rate_limit_events": [
            {
                "id": row.id,
                "action": row.action,
                "created_at": row.created_at,
                "identifier_hash": row.identifier_hash,
                "ip_hash": row.ip_hash,
            }
            for row in auth_events
        ],
    }


@router.get("/leagues/{league_id}/diagnostics")
def league_diagnostics(
    league_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin_user),
) -> dict:
    league = db.get(League, league_id)
    if not league:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league not found")
    teams = db.query(Team).filter(Team.league_id == league_id).all()
    members = db.query(LeagueMember).filter(LeagueMember.league_id == league_id).all()
    scoring_runs = (
        db.query(ScoringRun)
        .filter(ScoringRun.league_id == league_id)
        .order_by(ScoringRun.started_at.desc(), ScoringRun.id.desc())
        .limit(10)
        .all()
    )
    audits = (
        db.query(AuditEvent)
        .filter(AuditEvent.league_id == league_id)
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .limit(25)
        .all()
    )
    return {
        "league": {
            "id": league.id,
            "name": league.name,
            "status": league.status,
            "season_year": league.season_year,
            "max_teams": league.max_teams,
            "commissioner_user_id": league.commissioner_user_id,
            "created_at": league.created_at,
            "updated_at": league.updated_at,
        },
        "counts": {
            "teams": len(teams),
            "members": len(members),
            "recent_scoring_runs": len(scoring_runs),
            "recent_audit_events": len(audits),
        },
        "teams": [
            {"id": row.id, "name": row.name, "owner_user_id": row.owner_user_id, "owner_name": row.owner_name}
            for row in teams
        ],
        "members": [
            {"id": row.id, "user_id": row.user_id, "role": row.role, "joined_at": row.joined_at}
            for row in members
        ],
        "recent_scoring_runs": [_failed_scoring_run(row) | {"status": row.status} for row in scoring_runs],
        "recent_audit_events": [_audit_event(row) for row in audits],
    }
