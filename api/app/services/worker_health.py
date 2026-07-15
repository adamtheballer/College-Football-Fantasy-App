from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.worker_heartbeat import WorkerHeartbeat


def record_worker_heartbeat(
    db: Session,
    *,
    worker_name: str,
    success: bool,
    details: dict | None = None,
) -> WorkerHeartbeat:
    now = datetime.now(timezone.utc)
    row = db.query(WorkerHeartbeat).filter(WorkerHeartbeat.worker_name == worker_name).first()
    if row is None:
        row = WorkerHeartbeat(worker_name=worker_name)
        db.add(row)
    row.status = "healthy" if success else "failed"
    row.heartbeat_at = now
    row.details_json = details or {}
    if success:
        row.last_success_at = now
    else:
        row.last_failure_at = now
    db.commit()
    return row
