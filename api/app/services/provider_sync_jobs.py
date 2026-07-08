from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.provider_sync_job import ProviderSyncJob


def start_provider_sync_job(
    db: Session,
    *,
    provider: str,
    feed: str,
    season: int | None = None,
    week: int | None = None,
    scope: str = "global",
) -> ProviderSyncJob:
    job = ProviderSyncJob(
        provider=provider,
        feed=feed,
        season=season,
        week=week,
        scope=scope,
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.flush()
    return job


def finish_provider_sync_job(
    db: Session,
    job: ProviderSyncJob,
    *,
    status: str,
    rows_seen: int = 0,
    rows_inserted: int = 0,
    rows_updated: int = 0,
    rows_rejected: int = 0,
    error_summary: str | None = None,
) -> ProviderSyncJob:
    job.status = status
    job.finished_at = datetime.now(timezone.utc)
    job.rows_seen = rows_seen
    job.rows_inserted = rows_inserted
    job.rows_updated = rows_updated
    job.rows_rejected = rows_rejected
    job.error_summary = error_summary
    db.add(job)
    db.flush()
    return job


def run_provider_sync_job(
    db: Session,
    *,
    provider: str,
    feed: str,
    season: int | None,
    week: int | None,
    scope: str = "global",
    operation: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    job = start_provider_sync_job(db, provider=provider, feed=feed, season=season, week=week, scope=scope)
    try:
        result = operation()
    except Exception as exc:
        finish_provider_sync_job(db, job, status="failed", error_summary=str(exc))
        raise

    rows_seen = int(result.get("rows_seen", 0) or 0)
    rows_rejected = int(result.get("rows_rejected", result.get("skipped", 0)) or 0)
    rows_inserted = int(result.get("inserted", result.get("rows_inserted", 0)) or 0)
    rows_updated = int(result.get("updated", result.get("rows_updated", 0)) or 0)
    status = "success"
    if result.get("error_summary"):
        status = "partial"
    finish_provider_sync_job(
        db,
        job,
        status=status,
        rows_seen=rows_seen,
        rows_inserted=rows_inserted,
        rows_updated=rows_updated,
        rows_rejected=rows_rejected,
        error_summary=result.get("error_summary"),
    )
    result["provider_sync_job_id"] = job.id
    return result
