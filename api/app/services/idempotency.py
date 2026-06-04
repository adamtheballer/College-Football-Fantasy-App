from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from api.app.models.idempotency_request import IdempotencyRequest


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class IdempotencyStart:
    enabled: bool
    replay: bool
    row: IdempotencyRequest | None = None
    response_status_code: int | None = None
    response_payload: dict[str, Any] | None = None


def begin_idempotent_request(
    db: Session,
    *,
    scope: str,
    idempotency_key: str | None,
    created_by_user_id: int | None,
) -> IdempotencyStart:
    resolved_key = (idempotency_key or "").strip()
    if not resolved_key:
        return IdempotencyStart(enabled=False, replay=False)

    row = (
        db.query(IdempotencyRequest)
        .filter(
            IdempotencyRequest.scope == scope,
            IdempotencyRequest.idempotency_key == resolved_key,
        )
        .first()
    )
    if row:
        if row.status == "completed" and row.response_payload is not None and row.response_status_code is not None:
            return IdempotencyStart(
                enabled=True,
                replay=True,
                row=row,
                response_status_code=int(row.response_status_code),
                response_payload=dict(row.response_payload),
            )
        if row.status == "in_progress":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="identical request is already in progress",
            )
        # allow retry if previous attempt failed
        row.status = "in_progress"
        row.response_status_code = None
        row.response_payload = None
        row.completed_at = None
        row.updated_at = _utc_now()
        db.add(row)
        db.flush()
        return IdempotencyStart(enabled=True, replay=False, row=row)

    row = IdempotencyRequest(
        scope=scope,
        idempotency_key=resolved_key,
        status="in_progress",
        created_by_user_id=created_by_user_id,
    )
    db.add(row)
    db.flush()
    return IdempotencyStart(enabled=True, replay=False, row=row)


def get_completed_idempotent_response(
    db: Session,
    *,
    scope: str,
    idempotency_key: str | None,
) -> tuple[int, dict[str, Any]] | None:
    resolved_key = (idempotency_key or "").strip()
    if not resolved_key:
        return None
    row = (
        db.query(IdempotencyRequest)
        .filter(
            IdempotencyRequest.scope == scope,
            IdempotencyRequest.idempotency_key == resolved_key,
            IdempotencyRequest.status == "completed",
        )
        .first()
    )
    if not row or row.response_status_code is None or row.response_payload is None:
        return None
    return int(row.response_status_code), dict(row.response_payload)


def complete_idempotent_request(
    db: Session,
    *,
    start: IdempotencyStart,
    response_status_code: int,
    response_payload: dict[str, Any],
) -> None:
    if not start.enabled or start.row is None:
        return
    row = start.row
    row.status = "completed"
    row.response_status_code = int(response_status_code)
    row.response_payload = response_payload
    row.completed_at = _utc_now()
    row.updated_at = _utc_now()
    db.add(row)
    db.flush()


def fail_idempotent_request(
    db: Session,
    *,
    start: IdempotencyStart,
) -> None:
    if not start.enabled or start.row is None:
        return
    row = start.row
    row.status = "failed"
    row.updated_at = _utc_now()
    db.add(row)
    db.flush()
