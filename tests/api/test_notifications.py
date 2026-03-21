from datetime import datetime, timezone

from collegefootballfantasy_api.app.models.notification import NotificationDeliveryAttempt
from collegefootballfantasy_api.app.models.scheduled_notification import ScheduledNotification
from collegefootballfantasy_api.app.services.notification_service import record_delivery_attempt


def create_user(client, suffix: str = "one") -> dict:
    response = client.post(
        "/auth/signup",
        json={
            "first_name": f"Coach{suffix}",
            "email": f"coach-{suffix}@example.com",
            "password": "secret123",
        },
    )
    assert response.status_code == 201
    return response.json()["user"]


def create_league(client, token: str, name: str = "Notify League") -> dict:
    payload = {
        "basics": {
            "name": name,
            "season_year": 2026,
            "max_teams": 12,
            "is_private": True,
            "description": "Notifications league",
            "icon_url": None,
        },
        "settings": {
            "scoring_json": {"ppr": 1},
            "roster_slots_json": {"QB": 1},
            "playoff_teams": 4,
            "waiver_type": "faab",
            "trade_review_type": "commissioner",
            "superflex_enabled": False,
            "kicker_enabled": True,
            "defense_enabled": False,
        },
        "draft": {
            "draft_datetime_utc": "2026-08-19T18:00:00Z",
            "timezone": "America/Los_Angeles",
            "draft_type": "snake",
            "pick_timer_seconds": 90,
        },
    }
    response = client.post("/leagues", json=payload, headers={"X-User-Token": token})
    assert response.status_code == 201
    return response.json()["league"]


def test_notification_preferences_are_auth_scoped_without_user_key(client):
    user = create_user(client, "prefs")
    token = user["api_token"]

    initial_response = client.get("/notifications/preferences", headers={"X-User-Token": token})
    assert initial_response.status_code == 200
    assert "user_key" not in initial_response.json()

    update_response = client.post(
        "/notifications/preferences",
        json={
            "push_enabled": False,
            "email_enabled": True,
            "draft_alerts": False,
            "injury_alerts": True,
            "touchdown_alerts": True,
            "usage_alerts": False,
            "waiver_alerts": True,
            "projection_alerts": False,
            "lineup_reminders": True,
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "07:00",
        },
        headers={"X-User-Token": token},
    )
    assert update_response.status_code == 200
    body = update_response.json()
    assert "user_key" not in body
    assert body["push_enabled"] is False
    assert body["touchdown_alerts"] is True
    assert body["quiet_hours_start"] == "22:00"


def test_push_tokens_and_league_preferences_resolve_identity_from_auth(client):
    user = create_user(client, "notify")
    token = user["api_token"]
    league = create_league(client, token)

    token_response = client.post(
        "/notifications/tokens",
        json={"device_token": "device-123", "platform": "ios"},
        headers={"X-User-Token": token},
    )
    assert token_response.status_code == 200
    assert token_response.json()["user_id"] == user["id"]

    prefs_response = client.get("/notifications/league-preferences", headers={"X-User-Token": token})
    assert prefs_response.status_code == 200
    assert prefs_response.json()["data"][0]["league_id"] == league["id"]

    update_response = client.post(
        "/notifications/league-preferences",
        json={
            "items": [
                {
                    "league_id": league["id"],
                    "enabled": True,
                    "injury_alerts": False,
                    "big_play_alerts": True,
                    "projection_alerts": False,
                }
            ]
        },
        headers={"X-User-Token": token},
    )
    assert update_response.status_code == 200
    updated = update_response.json()["data"][0]
    assert updated["league_id"] == league["id"]
    assert updated["injury_alerts"] is False
    assert updated["projection_alerts"] is False


def test_league_create_queues_pending_notification_delivery_attempts(client, db_session):
    user = create_user(client, "deliveries")
    league = create_league(client, user["api_token"], "Delivery League")

    scheduled_rows = (
        db_session.query(ScheduledNotification)
        .filter(
            ScheduledNotification.league_id == league["id"],
            ScheduledNotification.user_id == user["id"],
        )
        .order_by(ScheduledNotification.notification_type.asc())
        .all()
    )
    assert len(scheduled_rows) == 2

    attempts = (
        db_session.query(NotificationDeliveryAttempt)
        .join(
            ScheduledNotification,
            ScheduledNotification.id == NotificationDeliveryAttempt.scheduled_notification_id,
        )
        .filter(
            ScheduledNotification.league_id == league["id"],
            NotificationDeliveryAttempt.user_id == user["id"],
        )
        .all()
    )
    assert len(attempts) == 4
    assert {attempt.channel for attempt in attempts} == {"push", "email"}
    assert {attempt.status for attempt in attempts} == {"pending"}


def test_draft_reschedule_cancels_old_notification_attempts_and_queues_new_ones(client, db_session):
    user = create_user(client, "reschedule")
    league = create_league(client, user["api_token"], "Reschedule League")
    original_ids = {
        row.id
        for row in db_session.query(ScheduledNotification)
        .filter(ScheduledNotification.league_id == league["id"])
        .all()
    }
    assert len(original_ids) == 2

    response = client.patch(
        f"/leagues/{league['id']}/draft",
        json={
            "draft_datetime_utc": "2026-08-20T18:00:00Z",
            "timezone": "America/Los_Angeles",
            "draft_type": "snake",
            "pick_timer_seconds": 120,
            "status": "scheduled",
        },
        headers={"X-User-Token": user["api_token"]},
    )
    assert response.status_code == 200

    all_scheduled = (
        db_session.query(ScheduledNotification)
        .filter(ScheduledNotification.league_id == league["id"])
        .order_by(ScheduledNotification.id.asc())
        .all()
    )
    assert len(all_scheduled) == 4

    canceled_rows = [row for row in all_scheduled if row.id in original_ids]
    replacement_rows = [row for row in all_scheduled if row.id not in original_ids]
    assert len(canceled_rows) == 2
    assert len(replacement_rows) == 2
    assert all(row.canceled_at is not None for row in canceled_rows)
    assert all(row.canceled_at is None for row in replacement_rows)

    canceled_attempts = (
        db_session.query(NotificationDeliveryAttempt)
        .filter(NotificationDeliveryAttempt.scheduled_notification_id.in_(list(original_ids)))
        .all()
    )
    assert len(canceled_attempts) == 4
    assert {attempt.status for attempt in canceled_attempts} == {"canceled"}

    replacement_attempts = (
        db_session.query(NotificationDeliveryAttempt)
        .filter(
            NotificationDeliveryAttempt.scheduled_notification_id.in_([row.id for row in replacement_rows])
        )
        .all()
    )
    assert len(replacement_attempts) == 4
    assert {attempt.status for attempt in replacement_attempts} == {"pending"}


def test_delivery_attempts_only_mark_scheduled_row_sent_after_terminal_results(client, db_session):
    user = create_user(client, "finalize")
    league = create_league(client, user["api_token"], "Finalize League")
    scheduled = (
        db_session.query(ScheduledNotification)
        .filter(
            ScheduledNotification.league_id == league["id"],
            ScheduledNotification.user_id == user["id"],
            ScheduledNotification.notification_type == "draft_start",
        )
        .first()
    )
    assert scheduled is not None

    record_delivery_attempt(
        db_session,
        scheduled_notification_id=scheduled.id,
        channel="push",
        status="failed",
        error_message="provider timeout",
    )
    db_session.commit()
    db_session.refresh(scheduled)
    assert scheduled.sent_at is None

    record_delivery_attempt(
        db_session,
        scheduled_notification_id=scheduled.id,
        channel="email",
        status="delivered",
        delivered_at=datetime(2026, 8, 19, 17, 5, tzinfo=timezone.utc),
    )
    db_session.commit()
    db_session.refresh(scheduled)
    assert scheduled.sent_at is not None
