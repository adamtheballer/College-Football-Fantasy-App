from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.notification import NotificationDeliveryAttempt
from collegefootballfantasy_api.app.models.scheduled_notification import ScheduledNotification
from collegefootballfantasy_api.app.services.notification_dedupe import make_notification_dedupe_key
from collegefootballfantasy_api.app.services.notification_service import (
    create_notification_event,
    record_delivery_attempt,
)


@dataclass(frozen=True)
class NotificationDeliverySummary:
    scheduled_seen: int = 0
    delivered: int = 0
    skipped: int = 0
    failed: int = 0


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _title_for_scheduled(notification_type: str) -> str:
    if notification_type == "draft_1h":
        return "Draft Starts Soon"
    if notification_type == "draft_start":
        return "Draft Is Live"
    return notification_type.replace("_", " ").title()


def _body_for_scheduled(notification_type: str) -> str:
    if notification_type == "draft_1h":
        return "Your league draft starts in one hour."
    if notification_type == "draft_start":
        return "Your league draft is ready to start."
    return "You have a scheduled league notification."


def deliver_due_scheduled_notifications(db: Session, *, now: datetime | None = None) -> NotificationDeliverySummary:
    now = now or _utc_now()
    rows = (
        db.query(ScheduledNotification)
        .filter(
            ScheduledNotification.scheduled_for <= now,
            ScheduledNotification.sent_at.is_(None),
            ScheduledNotification.canceled_at.is_(None),
        )
        .order_by(ScheduledNotification.scheduled_for.asc(), ScheduledNotification.id.asc())
        .all()
    )
    delivered = 0
    skipped = 0
    failed = 0
    for row in rows:
        existing_in_app_attempt = (
            db.query(NotificationDeliveryAttempt)
            .filter(
                NotificationDeliveryAttempt.scheduled_notification_id == row.id,
                NotificationDeliveryAttempt.channel == "in_app",
                NotificationDeliveryAttempt.status.in_(["delivered", "skipped"]),
            )
            .first()
        )
        if existing_in_app_attempt:
            skipped += 1
            continue
        dedupe_key = make_notification_dedupe_key(
            alert_type=row.notification_type,
            source_entity_type="scheduled_notification",
            source_entity_id=row.id,
            user_id=row.user_id,
        )
        try:
            notification = create_notification_event(
                db,
                user_id=row.user_id,
                league_id=row.league_id,
                alert_type=row.notification_type,
                title=_title_for_scheduled(row.notification_type),
                body=_body_for_scheduled(row.notification_type),
                payload={"league_id": row.league_id, "scheduled_notification_id": row.id},
                dedupe_key=dedupe_key,
                source_entity_type="scheduled_notification",
                source_entity_id=row.id,
                deep_link=f"/leagues/{row.league_id}/draft",
            )
            if notification is None:
                record_delivery_attempt(
                    db,
                    scheduled_notification_id=row.id,
                    channel="in_app",
                    status="skipped",
                    error_message="notification preferences disabled",
                )
                skipped += 1
            else:
                record_delivery_attempt(
                    db,
                    scheduled_notification_id=row.id,
                    channel="in_app",
                    status="delivered",
                    delivered_at=now,
                )
                delivered += 1
        except Exception as exc:
            record_delivery_attempt(
                db,
                scheduled_notification_id=row.id,
                channel="in_app",
                status="failed",
                error_message=str(exc)[:500],
            )
            failed += 1
    db.commit()
    return NotificationDeliverySummary(scheduled_seen=len(rows), delivered=delivered, skipped=skipped, failed=failed)
