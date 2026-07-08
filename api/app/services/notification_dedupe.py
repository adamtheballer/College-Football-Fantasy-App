from __future__ import annotations

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.notification import NotificationLog
from collegefootballfantasy_api.app.services.notification_service import legacy_user_key


def find_duplicate_notification(
    db: Session,
    *,
    user_id: int,
    dedupe_key: str | None,
) -> NotificationLog | None:
    if not dedupe_key:
        return None
    return (
        db.query(NotificationLog)
        .filter(NotificationLog.user_id == user_id, NotificationLog.dedupe_key == dedupe_key)
        .first()
    )


def make_notification_dedupe_key(*, alert_type: str, source_entity_type: str, source_entity_id: int, user_id: int) -> str:
    return f"{legacy_user_key(user_id)}:{alert_type}:{source_entity_type}:{source_entity_id}"
