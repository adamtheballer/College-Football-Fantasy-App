from __future__ import annotations

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.draft_event import DraftEvent


def record_draft_event(
    db: Session,
    *,
    draft: Draft,
    league_id: int,
    event_type: str,
    team_id: int | None = None,
    actor_user_id: int | None = None,
    payload: dict | None = None,
) -> DraftEvent:
    row = DraftEvent(
        league_id=league_id,
        draft_id=draft.id,
        team_id=team_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        payload_json=payload,
    )
    db.add(row)
    return row
