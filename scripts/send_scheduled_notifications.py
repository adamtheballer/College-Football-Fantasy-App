import argparse
import os
import sys
from datetime import datetime, timezone

import httpx
from sqlalchemy import and_, select

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.notification import NotificationLog, NotificationPreference, PushToken
from collegefootballfantasy_api.app.models.scheduled_notification import ScheduledNotification
from collegefootballfantasy_api.app.models.user import User


EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
RESEND_URL = "https://api.resend.com/emails"


def _notification_copy(notification_type: str, league_name: str) -> tuple[str, str]:
    if notification_type == "draft_1h":
        return (
            f"Draft Reminder - {league_name}",
            f"Your draft for {league_name} starts in 1 hour.",
        )
    if notification_type == "draft_start":
        return (
            f"Draft Starting - {league_name}",
            f"Your draft for {league_name} is starting now.",
        )
    return ("League Alert", "You have a new league update.")


def send_push(token: str, title: str, body: str, data: dict | None = None) -> None:
    payload = {
        "to": token,
        "title": title,
        "body": body,
        "data": data or {},
    }
    httpx.post(EXPO_PUSH_URL, json=payload, timeout=10.0)


def send_email(email: str, title: str, body: str) -> None:
    api_key = os.getenv("RESEND_API_KEY")
    from_email = os.getenv("RESEND_FROM")
    if not api_key or not from_email:
        return
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {
        "from": from_email,
        "to": [email],
        "subject": title,
        "html": f"<p>{body}</p>",
    }
    httpx.post(RESEND_URL, json=payload, headers=headers, timeout=10.0)


def main() -> None:
    parser = argparse.ArgumentParser(description="Send scheduled league notifications.")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    session = SessionLocal()
    try:
        rows = session.execute(
            select(ScheduledNotification)
            .where(
                and_(
                    ScheduledNotification.sent_at.is_(None),
                    ScheduledNotification.canceled_at.is_(None),
                    ScheduledNotification.scheduled_for <= now,
                )
            )
            .limit(args.limit)
        ).scalars().all()

        for row in rows:
            league = session.get(League, row.league_id)
            user = session.get(User, row.user_id)
            if not league or not user:
                continue

            prefs = session.execute(
                select(NotificationPreference).where(NotificationPreference.user_key == str(user.id))
            ).scalar_one_or_none()
            if prefs and not prefs.draft_alerts:
                row.sent_at = now
                continue

            title, body = _notification_copy(row.notification_type, league.name)

            if not args.dry_run:
                session.add(
                    NotificationLog(
                        user_key=str(user.id),
                        alert_type=row.notification_type,
                        title=title,
                        body=body,
                        payload={"league_id": league.id},
                        sent_at=now,
                    )
                )

                if not prefs or prefs.push_enabled:
                    tokens = session.execute(
                        select(PushToken).where(PushToken.user_key == str(user.id), PushToken.enabled.is_(True))
                    ).scalars().all()
                    for token in tokens:
                        send_push(token.device_token, title, body, {"leagueId": league.id})

                if not prefs or prefs.email_enabled:
                    send_email(user.email, title, body)

            row.sent_at = now

        if not args.dry_run:
            session.commit()
    finally:
        session.close()


if __name__ == "__main__":
    main()
