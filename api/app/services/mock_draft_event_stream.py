from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.mock_draft_event import MockDraftEvent


def append_mock_draft_event(
    db: Session,
    *,
    session_id: int,
    event_type: str,
    payload: dict[str, Any] | None = None,
    entity_type: str = "mock_draft",
    entity_id: int | None = None,
    schema_version: int = 1,
) -> MockDraftEvent:
    event = MockDraftEvent(
        session_id=session_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        schema_version=schema_version,
        payload=payload or {},
        occurred_at=datetime.now(timezone.utc),
    )
    db.add(event)
    db.flush()
    return event


def list_mock_draft_events_since(
    db: Session,
    *,
    session_id: int,
    since_seq: int = 0,
    limit: int = 250,
) -> list[MockDraftEvent]:
    resolved_limit = max(1, min(limit, 500))
    return (
        db.query(MockDraftEvent)
        .filter(MockDraftEvent.session_id == session_id, MockDraftEvent.id > since_seq)
        .order_by(MockDraftEvent.id.asc())
        .limit(resolved_limit)
        .all()
    )


def latest_mock_draft_event_seq(db: Session, *, session_id: int) -> int:
    latest = (
        db.query(MockDraftEvent.id)
        .filter(MockDraftEvent.session_id == session_id)
        .order_by(MockDraftEvent.id.desc())
        .first()
    )
    if not latest:
        return 0
    return int(latest[0])
