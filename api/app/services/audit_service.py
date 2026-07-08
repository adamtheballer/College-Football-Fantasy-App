from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Mapping

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.audit_event import AuditEvent


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def record_audit_event(
    db: Session,
    *,
    action: str,
    entity_type: str,
    actor_user_id: int | None = None,
    league_id: int | None = None,
    team_id: int | None = None,
    entity_id: int | str | None = None,
    before: Mapping[str, Any] | None = None,
    after: Mapping[str, Any] | None = None,
    request_id: str | None = None,
    ip_hash: str | None = None,
    user_agent_hash: str | None = None,
) -> AuditEvent:
    event = AuditEvent(
        actor_user_id=actor_user_id,
        league_id=league_id,
        team_id=team_id,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        action=action,
        before_json=_json_safe(before) if before is not None else None,
        after_json=_json_safe(after) if after is not None else None,
        request_id=request_id,
        ip_hash=ip_hash,
        user_agent_hash=user_agent_hash,
    )
    db.add(event)
    return event
