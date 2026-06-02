from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.domain_event import DomainEvent


def append_league_event(
    db: Session,
    *,
    league_id: int,
    event_type: str,
    payload: dict[str, Any] | None = None,
    entity_type: str = "league",
    entity_id: int | None = None,
    schema_version: int = 1,
) -> DomainEvent:
    event = DomainEvent(
        league_id=league_id,
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


def list_league_events_since(
    db: Session,
    *,
    league_id: int,
    since_seq: int = 0,
    limit: int = 250,
) -> list[DomainEvent]:
    resolved_limit = max(1, min(limit, 500))
    return (
        db.query(DomainEvent)
        .filter(DomainEvent.league_id == league_id, DomainEvent.id > since_seq)
        .order_by(DomainEvent.id.asc())
        .limit(resolved_limit)
        .all()
    )


def latest_league_event_seq(db: Session, *, league_id: int) -> int:
    latest = (
        db.query(DomainEvent.id)
        .filter(DomainEvent.league_id == league_id)
        .order_by(DomainEvent.id.desc())
        .first()
    )
    if not latest:
        return 0
    return int(latest[0])
