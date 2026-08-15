from datetime import datetime, timedelta, timezone

from conftest import TestingSessionLocal
from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.models.notification import (
    NotificationDeliveryAttempt,
    NotificationLog,
    NotificationPreference,
    PushToken,
)
from collegefootballfantasy_api.app.models.lineup_week_snapshot import LineupWeekSnapshot
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.scheduled_notification import ScheduledNotification
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.services.notification_providers import (
    FakeEmailProvider,
    FakePushProvider,
    ProviderDeliveryResult,
)
from collegefootballfantasy_api.app.services.notification_service import (
    process_due_notifications_once,
    intake_typed_big_play_notification,
    queue_certified_matchup_final_notifications,
    queue_notification_event,
    record_delivery_attempt,
    rebuild_matchup_start_notifications,
)


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def create_user(client, suffix: str = "one") -> dict:
    response = client.post(
        "/auth/signup",
        json={
            "first_name": f"Coach{suffix}",
            "email": f"coach-{suffix}@example.com",
            "password": "StrongPass123!",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    with TestingSessionLocal() as session:
        user = session.query(User).filter(User.email == f"coach-{suffix}@example.com").one()
        user.email_verified_at = datetime.now(timezone.utc)
        session.commit()
    return {"user": payload["user"], "access_token": payload["access_token"]}


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
    response = client.post("/leagues", json=payload, headers=auth_headers(token))
    assert response.status_code == 201
    return response.json()["league"]


def test_notification_preferences_are_auth_scoped_without_user_key(client):
    identity = create_user(client, "prefs")
    user = identity["user"]
    token = identity["access_token"]

    initial_response = client.get("/notifications/preferences", headers=auth_headers(token))
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
        headers=auth_headers(token),
    )
    assert update_response.status_code == 200
    body = update_response.json()
    assert "user_key" not in body
    assert body["push_enabled"] is False
    assert body["touchdown_alerts"] is True
    assert body["quiet_hours_start"] == "22:00"


def test_push_tokens_and_league_preferences_resolve_identity_from_auth(client):
    identity = create_user(client, "notify")
    user = identity["user"]
    token = identity["access_token"]
    league = create_league(client, token)

    token_response = client.post(
        "/notifications/tokens",
        json={"device_token": "device-123", "platform": "ios"},
        headers=auth_headers(token),
    )
    assert token_response.status_code == 200
    assert token_response.json()["user_id"] == user["id"]

    prefs_response = client.get("/notifications/league-preferences", headers=auth_headers(token))
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
        headers=auth_headers(token),
    )
    assert update_response.status_code == 200
    updated = update_response.json()["data"][0]
    assert updated["league_id"] == league["id"]
    assert updated["injury_alerts"] is False
    assert updated["projection_alerts"] is False


def test_push_subscription_cannot_be_taken_over_by_another_user(client, db_session):
    owner = create_user(client, "subscription-owner")
    other = create_user(client, "subscription-other")
    created = client.post(
        "/notifications/tokens",
        json={"subscription_id": "subscription-owned-by-owner", "platform": "web"},
        headers=auth_headers(owner["access_token"]),
    )
    assert created.status_code == 200

    takeover = client.post(
        "/notifications/tokens",
        json={"subscription_id": "subscription-owned-by-owner", "platform": "web"},
        headers=auth_headers(other["access_token"]),
    )
    assert takeover.status_code == 404
    stored = db_session.query(PushToken).filter(PushToken.id == created.json()["id"]).one()
    assert stored.user_id == owner["user"]["id"]
    assert stored.enabled is True


def test_league_create_queues_pending_notification_delivery_attempts(client, db_session):
    identity = create_user(client, "deliveries")
    user = identity["user"]
    league = create_league(client, identity["access_token"], "Delivery League")

    scheduled_rows = (
        db_session.query(ScheduledNotification)
        .filter(
            ScheduledNotification.league_id == league["id"],
            ScheduledNotification.user_id == user["id"],
        )
        .order_by(ScheduledNotification.notification_type.asc())
        .all()
    )
    assert len(scheduled_rows) == 1
    assert scheduled_rows[0].event_type == "DRAFT_1H"

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
    assert len(attempts) == 3
    assert {attempt.channel for attempt in attempts} == {"in_app", "push", "email"}
    assert {attempt.status for attempt in attempts} == {"pending"}


def test_draft_reschedule_cancels_old_notification_attempts_and_queues_new_ones(client, db_session):
    identity = create_user(client, "reschedule")
    user = identity["user"]
    league = create_league(client, identity["access_token"], "Reschedule League")
    original_ids = {
        row.id
        for row in db_session.query(ScheduledNotification)
        .filter(ScheduledNotification.league_id == league["id"])
        .all()
    }
    assert len(original_ids) == 1

    response = client.patch(
        f"/leagues/{league['id']}/draft",
        json={
            "draft_datetime_utc": "2026-08-20T18:00:00Z",
            "timezone": "America/Los_Angeles",
            "draft_type": "snake",
            "pick_timer_seconds": 120,
            "status": "scheduled",
        },
        headers=auth_headers(identity["access_token"]),
    )
    assert response.status_code == 200

    all_scheduled = (
        db_session.query(ScheduledNotification)
        .filter(ScheduledNotification.league_id == league["id"])
        .order_by(ScheduledNotification.id.asc())
        .all()
    )
    assert len(all_scheduled) == 3

    canceled_rows = [row for row in all_scheduled if row.id in original_ids]
    replacement_rows = [row for row in all_scheduled if row.id not in original_ids]
    assert len(canceled_rows) == 1
    # The replacement one-hour reminder plus the informational reschedule event.
    assert len(replacement_rows) == 2
    assert all(row.canceled_at is not None for row in canceled_rows)
    assert all(row.canceled_at is None for row in replacement_rows)

    canceled_attempts = (
        db_session.query(NotificationDeliveryAttempt)
        .filter(NotificationDeliveryAttempt.scheduled_notification_id.in_(list(original_ids)))
        .all()
    )
    assert len(canceled_attempts) == 3
    assert {attempt.status for attempt in canceled_attempts} == {"canceled"}

    replacement_attempts = (
        db_session.query(NotificationDeliveryAttempt)
        .filter(
            NotificationDeliveryAttempt.scheduled_notification_id.in_([row.id for row in replacement_rows])
        )
        .all()
    )
    assert len(replacement_attempts) == 6
    assert {attempt.status for attempt in replacement_attempts} == {"pending"}


def test_delivery_attempts_only_mark_scheduled_row_sent_after_terminal_results(client, db_session):
    identity = create_user(client, "finalize")
    user = identity["user"]
    league = create_league(client, identity["access_token"], "Finalize League")
    scheduled = (
        db_session.query(ScheduledNotification)
        .filter(
            ScheduledNotification.league_id == league["id"],
            ScheduledNotification.user_id == user["id"],
            ScheduledNotification.event_type == "DRAFT_1H",
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
    assert scheduled.sent_at is None


def test_direct_user_notification_is_visible_without_a_rostered_player(client, db_session):
    identity = create_user(client, "direct-alert")
    user = identity["user"]
    league = create_league(client, identity["access_token"], "Direct Alert League")
    db_session.add(
        NotificationLog(
            user_id=user["id"],
            user_key=str(user["id"]),
            alert_type="DRAFT_START",
            category="DRAFT",
            title="Your draft is starting",
            body="Your private draft is ready.",
            league_id=league["id"],
            payload={"destination": {"type": "draft", "league_id": league["id"]}},
        )
    )
    db_session.commit()

    response = client.get("/notifications/alerts", headers=auth_headers(identity["access_token"]))
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["unread_count"] == 1
    assert response.json()["data"][0]["destination"] == {"type": "draft", "league_id": league["id"], "resource_id": None}


def test_category_preference_suppresses_in_app_and_external_delivery(client, db_session):
    identity = create_user(client, "disabled-draft-alerts")
    league = create_league(client, identity["access_token"], "Disabled Draft Alerts")
    user_id = identity["user"]["id"]
    db_session.add(
        NotificationPreference(
            user_id=user_id,
            user_key=str(user_id),
            draft_alerts=False,
        )
    )
    queue_notification_event(
        db_session,
        league_id=league["id"],
        user_id=user_id,
        event_type="DRAFT_START",
        event_key=f"draft:disabled:{user_id}",
    )
    db_session.commit()

    process_due_notifications_once(db_session, now=datetime.now(timezone.utc) + timedelta(seconds=1))
    assert db_session.query(NotificationLog).filter(NotificationLog.user_id == user_id).count() == 0
    attempts = (
        db_session.query(NotificationDeliveryAttempt)
        .join(ScheduledNotification)
        .filter(ScheduledNotification.event_key == f"draft:disabled:{user_id}")
        .all()
    )
    assert {attempt.status for attempt in attempts} == {"skipped"}


def test_read_mutations_are_user_scoped_and_persist(client, db_session):
    first = create_user(client, "read-one")
    second = create_user(client, "read-two")
    own = NotificationLog(user_id=first["user"]["id"], user_key=str(first["user"]["id"]), alert_type="SYSTEM", category="SYSTEM", title="Own", body="Own")
    foreign = NotificationLog(user_id=second["user"]["id"], user_key=str(second["user"]["id"]), alert_type="SYSTEM", category="SYSTEM", title="Foreign", body="Foreign")
    db_session.add_all([own, foreign])
    db_session.commit()

    forbidden = client.patch(f"/notifications/alerts/{foreign.id}", json={"read": True}, headers=auth_headers(first["access_token"]))
    assert forbidden.status_code == 404
    marked = client.patch(f"/notifications/alerts/{own.id}", json={"read": True}, headers=auth_headers(first["access_token"]))
    assert marked.status_code == 200
    assert marked.json()["read_at"] is not None
    all_read = client.post("/notifications/alerts/read-all", headers=auth_headers(first["access_token"]))
    assert all_read.status_code == 200
    assert all_read.json()["updated"] == 0


def test_same_event_and_worker_replay_create_one_in_app_log_and_one_push(client, db_session, monkeypatch):
    identity = create_user(client, "outbox")
    league = create_league(client, identity["access_token"], "Outbox League")
    user_id = identity["user"]["id"]
    first = queue_notification_event(
        db_session,
        league_id=league["id"],
        user_id=user_id,
        event_type="TRADE_PROPOSED",
        event_key=f"trade:44:trade_proposed:{user_id}",
        payload={"trade_id": 44, "actor_name": "Manager A"},
    )
    same = queue_notification_event(
        db_session,
        league_id=league["id"],
        user_id=user_id,
        event_type="TRADE_PROPOSED",
        event_key=f"trade:44:trade_proposed:{user_id}",
        payload={"trade_id": 44, "actor_name": "Manager A"},
    )
    db_session.commit()
    assert first.id == same.id

    # A provider target is an immutable external user identity, but a local
    # OneSignal subscription must still be active before the worker attempts
    # push delivery.
    db_session.add(
        PushToken(
            user_id=user_id,
            user_key=str(user_id),
            device_token="subscription-outbox-test",
            provider="onesignal",
            external_user_id=f"cfb_user:{user_id}",
            platform="web",
            enabled=True,
        )
    )
    db_session.commit()
    monkeypatch.setattr(settings, "push_notifications_enabled", True)
    push = FakePushProvider()
    result = process_due_notifications_once(
        db_session,
        now=datetime.now(timezone.utc) + timedelta(seconds=1),
        push_provider=push,
        email_provider=FakeEmailProvider(),
    )
    assert result["delivered"] == 1
    assert result["provider_accepted"] == 1
    assert len(push.messages) == 1
    assert db_session.query(NotificationLog).filter(NotificationLog.user_id == user_id).count() == 1

    replay = process_due_notifications_once(
        db_session,
        now=datetime.now(timezone.utc) + timedelta(seconds=2),
        push_provider=push,
        email_provider=FakeEmailProvider(),
    )
    assert replay["claimed"] == 0
    assert len(push.messages) == 1


def test_retryable_push_failure_creates_a_bounded_retry_attempt(client, db_session, monkeypatch):
    identity = create_user(client, "retry-outbox")
    league = create_league(client, identity["access_token"], "Retry Outbox League")
    user_id = identity["user"]["id"]
    db_session.add(
        PushToken(
            user_id=user_id,
            user_key=str(user_id),
            device_token="subscription-retry-test",
            provider="onesignal",
            external_user_id=f"cfb_user:{user_id}",
            platform="web",
            enabled=True,
        )
    )
    queue_notification_event(
        db_session,
        league_id=league["id"],
        user_id=user_id,
        event_type="TRADE_PROPOSED",
        event_key=f"trade:retry:{user_id}",
        payload={"trade_id": 91},
    )
    db_session.commit()

    class RetryablePush:
        def send(self, **_kwargs):
            return ProviderDeliveryResult(accepted=False, retryable=True, error="provider timed out")

    monkeypatch.setattr(settings, "push_notifications_enabled", True)
    result = process_due_notifications_once(
        db_session,
        now=datetime.now(timezone.utc) + timedelta(seconds=1),
        push_provider=RetryablePush(),
        email_provider=FakeEmailProvider(),
    )
    assert result["retried"] == 1
    attempts = (
        db_session.query(NotificationDeliveryAttempt)
        .join(ScheduledNotification)
        .filter(ScheduledNotification.event_key == f"trade:retry:{user_id}", NotificationDeliveryAttempt.channel == "push")
        .order_by(NotificationDeliveryAttempt.attempt_number)
        .all()
    )
    assert [attempt.status for attempt in attempts] == ["retry", "pending"]
    assert attempts[-1].next_retry_at is not None


def test_exact_invalid_subscription_is_disabled_without_affecting_other_devices(client, db_session, monkeypatch):
    identity = create_user(client, "invalid-subscription")
    league = create_league(client, identity["access_token"], "Invalid Subscription League")
    user_id = identity["user"]["id"]
    invalid = PushToken(
        user_id=user_id,
        user_key=str(user_id),
        device_token="subscription-invalid",
        provider="onesignal",
        external_user_id=f"cfb_user:{user_id}",
        platform="web",
        enabled=True,
    )
    other = PushToken(
        user_id=user_id,
        user_key=str(user_id),
        device_token="subscription-still-valid",
        provider="onesignal",
        external_user_id=f"cfb_user:{user_id}",
        platform="web",
        enabled=True,
    )
    db_session.add_all([invalid, other])
    queue_notification_event(
        db_session,
        league_id=league["id"],
        user_id=user_id,
        event_type="TRADE_PROPOSED",
        event_key=f"trade:invalid-subscription:{user_id}",
        payload={"trade_id": 92},
    )
    db_session.commit()

    class InvalidSubscriptionPush:
        def send(self, **_kwargs):
            return ProviderDeliveryResult(
                accepted=False,
                invalid_subscription_id="subscription-invalid",
                error="subscription is no longer valid",
            )

    monkeypatch.setattr(settings, "push_notifications_enabled", True)
    process_due_notifications_once(
        db_session,
        now=datetime.now(timezone.utc) + timedelta(seconds=1),
        push_provider=InvalidSubscriptionPush(),
        email_provider=FakeEmailProvider(),
    )
    db_session.refresh(invalid)
    db_session.refresh(other)
    assert invalid.enabled is False
    assert other.enabled is True


def test_detach_allows_a_new_owner_without_deleting_subscription_history(client, db_session):
    first = create_user(client, "token-one")
    second = create_user(client, "token-two")
    payload = {"subscription_id": "subscription-123", "platform": "web", "provider": "onesignal"}
    response = client.post("/notifications/tokens", json=payload, headers=auth_headers(first["access_token"]))
    assert response.status_code == 200
    assert "subscription_id" not in response.json()

    protected = client.post("/notifications/tokens", json=payload, headers=auth_headers(second["access_token"]))
    assert protected.status_code == 404
    detached = client.post("/notifications/tokens/detach", json={}, headers=auth_headers(first["access_token"]))
    assert detached.status_code == 200
    assert detached.json() == {"disabled": 1}

    moved = client.post("/notifications/tokens", json=payload, headers=auth_headers(second["access_token"]))
    assert moved.status_code == 200
    rows = db_session.query(PushToken).filter(PushToken.device_token == "subscription-123").order_by(PushToken.id).all()
    assert len(rows) == 2
    assert rows[0].user_id == first["user"]["id"] and rows[0].enabled is False
    assert rows[1].user_id == second["user"]["id"] and rows[1].enabled is True


def test_matchup_start_rebuild_uses_only_verified_starters_and_reschedules_the_same_recipient_event(client, db_session):
    identity = create_user(client, "matchup-start")
    league = create_league(client, identity["access_token"], "Kickoff League")
    team = db_session.query(Team).filter_by(league_id=league["id"], owner_user_id=identity["user"]["id"]).one()
    player = Player(name="Kickoff QB", position="QB", school="Test")
    matchup = Matchup(
        league_id=league["id"], season=2026, week=1,
        home_team_id=team.id, away_team_id=team.id,
    )
    kickoff = datetime(2026, 8, 21, 18, tzinfo=timezone.utc)
    db_session.add(player)
    db_session.flush()
    snapshot = LineupWeekSnapshot(
        league_id=league["id"], team_id=team.id, player_id=player.id,
        season=2026, week=1, slot="QB", is_starter=True, game_start_at=kickoff,
    )
    roster = RosterEntry(league_id=league["id"], team_id=team.id, player_id=player.id, slot="QB", status="active")
    db_session.add_all([matchup, roster, snapshot])
    db_session.commit()

    assert rebuild_matchup_start_notifications(db_session, league_id=league["id"], season=2026, week=1) == 0
    db_session.commit()
    first = db_session.query(ScheduledNotification).filter_by(notification_type="MATCHUP_START").one()
    assert as_utc(first.scheduled_for) == kickoff

    snapshot.game_start_at = kickoff + timedelta(hours=1)
    db_session.commit()
    assert rebuild_matchup_start_notifications(db_session, league_id=league["id"], season=2026, week=1) == 1
    db_session.commit()
    rows = db_session.query(ScheduledNotification).filter_by(notification_type="MATCHUP_START").order_by(ScheduledNotification.id).all()
    assert len(rows) == 1
    assert rows[0].status == "pending"
    assert as_utc(rows[0].scheduled_for) == kickoff + timedelta(hours=1)


def test_certified_matchup_final_notifications_are_revision_idempotent(client, db_session):
    identity = create_user(client, "matchup-final")
    league = create_league(client, identity["access_token"], "Final League")
    team = db_session.query(Team).filter_by(league_id=league["id"], owner_user_id=identity["user"]["id"]).one()
    matchup = Matchup(
        league_id=league["id"], season=2026, week=1,
        home_team_id=team.id, away_team_id=team.id,
        status="final", home_score=21.0, away_score=17.0,
    )
    db_session.add(matchup)
    db_session.commit()

    assert queue_certified_matchup_final_notifications(db_session, matchup) == 1
    assert queue_certified_matchup_final_notifications(db_session, matchup) == 0
    matchup.status = "stat_corrected"
    matchup.home_score = 22.0
    assert queue_certified_matchup_final_notifications(db_session, matchup) == 1
    db_session.commit()
    assert db_session.query(ScheduledNotification).filter_by(notification_type="MATCHUP_FINAL").count() == 1
    corrected = db_session.query(ScheduledNotification).filter_by(notification_type="MATCHUP_CORRECTED").one()
    corrected_attempts = (
        db_session.query(NotificationDeliveryAttempt)
        .filter(NotificationDeliveryAttempt.scheduled_notification_id == corrected.id)
        .all()
    )
    assert {attempt.channel for attempt in corrected_attempts} == {"in_app"}


def test_certified_matchup_final_never_persists_a_tied_notification_outcome(client, db_session):
    identity = create_user(client, "matchup-no-tie")
    league = create_league(client, identity["access_token"], "No Tie League")
    team = db_session.query(Team).filter_by(league_id=league["id"], owner_user_id=identity["user"]["id"]).one()
    matchup = Matchup(
        league_id=league["id"], season=2026, week=1,
        home_team_id=team.id, away_team_id=team.id,
        status="final", home_score=21.0, away_score=21.0,
    )
    db_session.add(matchup)
    db_session.commit()

    assert queue_certified_matchup_final_notifications(db_session, matchup) == 1
    queued = db_session.query(ScheduledNotification).filter_by(notification_type="MATCHUP_FINAL").one()
    assert queued.payload["outcome"] is None
    assert queued.title == "Matchup final"
    assert queued.body == "Your Week 1 matchup is final."


def test_stale_claim_is_recovered_once_and_big_play_intake_is_disabled_by_default(client, db_session, monkeypatch):
    identity = create_user(client, "stale-claim")
    league = create_league(client, identity["access_token"], "Lease League")
    user_id = identity["user"]["id"]
    event = queue_notification_event(
        db_session,
        league_id=league["id"],
        user_id=user_id,
        event_type="TRADE_PROPOSED",
        event_key=f"trade:stale:{user_id}",
        payload={"trade_id": 7},
    )
    event.status = "claimed"
    event.claimed_by = "dead-worker"
    event.claimed_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    event.claim_heartbeat_at = event.claimed_at
    db_session.commit()

    result = process_due_notifications_once(db_session, worker_id="replacement-worker", now=datetime.now(timezone.utc))
    assert result["claimed"] == 1
    assert db_session.query(NotificationLog).filter_by(user_id=user_id, event_key=f"trade:stale:{user_id}:in_app").count() == 1

    monkeypatch.setattr(settings, "live_player_notifications_enabled", False)
    assert intake_typed_big_play_notification(
        db_session,
        league_id=league["id"],
        user_id=user_id,
        event_type="TOUCHDOWN",
        event_key=f"player:disabled:{user_id}",
        player_id=1,
    ) is None


def test_external_dead_letter_keeps_the_in_app_notification_and_sanitizes_error(client, db_session, monkeypatch):
    identity = create_user(client, "dead-letter")
    league = create_league(client, identity["access_token"], "Dead Letter League")
    user_id = identity["user"]["id"]
    db_session.add(
        PushToken(
            user_id=user_id,
            user_key=str(user_id),
            device_token="dead-letter-subscription",
            provider="onesignal",
            external_user_id=f"cfb_user:{user_id}",
            platform="web",
            enabled=True,
        )
    )
    queue_notification_event(
        db_session,
        league_id=league["id"],
        user_id=user_id,
        event_type="TRADE_PROPOSED",
        event_key=f"trade:dead-letter:{user_id}",
        payload={"trade_id": 8},
    )
    db_session.commit()

    class FailingPush:
        def send(self, **_kwargs):
            return ProviderDeliveryResult(accepted=False, retryable=False, error="provider error\nwith details")

    monkeypatch.setattr(settings, "push_notifications_enabled", True)
    process_due_notifications_once(
        db_session,
        now=datetime.now(timezone.utc),
        push_provider=FailingPush(),
        email_provider=FakeEmailProvider(),
    )
    event = db_session.query(ScheduledNotification).filter_by(event_key=f"trade:dead-letter:{user_id}").one()
    assert event.status == "dead_letter"
    assert db_session.query(NotificationLog).filter_by(user_id=user_id).count() == 1
    attempt = (
        db_session.query(NotificationDeliveryAttempt)
        .filter_by(scheduled_notification_id=event.id, channel="push")
        .one()
    )
    assert attempt.error_message == "provider error with details"
