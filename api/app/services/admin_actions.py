from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.admin_action import AdminAction


def append_admin_action(
    db: Session,
    *,
    league_id: int,
    actor_user_id: int | None,
    action_type: str,
    target_type: str = "league",
    target_id: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> AdminAction:
    row = AdminAction(
        league_id=league_id,
        actor_user_id=actor_user_id,
        action_type=action_type,
        target_type=target_type,
        target_id=target_id,
        meta=metadata or {},
    )
    db.add(row)
    db.flush()
    return row


def list_admin_actions(
    db: Session,
    *,
    league_id: int,
    since_id: int = 0,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AdminAction], int]:
    query = db.query(AdminAction).filter(AdminAction.league_id == league_id)
    if since_id > 0:
        query = query.filter(AdminAction.id > since_id)

    total = query.count()
    rows = (
        query.order_by(AdminAction.id.desc())
        .offset(max(0, offset))
        .limit(max(1, min(limit, 200)))
        .all()
    )
    return rows, total
