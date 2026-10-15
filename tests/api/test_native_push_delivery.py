from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import pytest
from sqlalchemy.exc import IntegrityError
from test_notifications import create_user, create_league, auth_headers
from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.models.notification import PushToken, NotificationPreference, NotificationDeliveryAttempt, NewsAnnouncement
from collegefootballfantasy_api.app.models.scheduled_notification import ScheduledNotification
from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.services.notification_providers import FakePushProvider, FakeEmailProvider, OneSignalPushProvider, ProviderDeliveryResult, verify_subscription_identity
from collegefootballfantasy_api.app.services.notification_service import queue_notification_event, process_due_notifications_once
from collegefootballfantasy_api.app.services.sportsdata_sync import _upsert_official_availability_rows


def seed(client, db, monkeypatch):
    identity = create_user(client, "native")
    league = create_league(client, identity["access_token"])
    user_id = identity["user"]["id"]
    tokens = [PushToken(user_id=user_id, user_key=str(user_id), device_token=f"phone-{n}", platform="ios", provider="onesignal", enabled=True) for n in range(2)]
    db.add_all(tokens)
    db.commit()
    monkeypatch.setattr(settings, "push_notifications_enabled", True)
    monkeypatch.setattr(settings, "push_provider", "fake")
    return identity, league, tokens


def event(db, identity, league, **kwargs):
    row = queue_notification_event(db, league_id=league["id"], user_id=identity["user"]["id"], event_type=kwargs.pop("event_type", "TRADE_PROPOSED"), event_key=kwargs.pop("event_key", f"test:{uuid4()}"), channels=("in_app", "push"), **kwargs)
    db.commit()
    return row


def dispatch(db, provider, **kwargs):
    return process_due_notifications_once(db, push_provider=provider, email_provider=FakeEmailProvider(), **kwargs)


def test_multiple_devices_have_stable_deduplicated_delivery_and_real_badge(client, db_session, monkeypatch):
    identity, league, tokens = seed(client, db_session, monkeypatch)
    row = event(db_session, identity, league)
    provider = FakePushProvider()
    dispatch(db_session, provider)
    dispatch(db_session, provider)
    assert len(provider.messages) == 2
    assert {m["subscription_id"] for m in provider.messages} == {t.device_token for t in tokens}
    assert len({m["idempotency_key"] for m in provider.messages}) == 2
    assert {m["badge_count"] for m in provider.messages} == {1}
    assert {m["data"]["recipient_user_id"] for m in provider.messages} == {identity["user"]["id"]}
    attempt = db_session.query(NotificationDeliveryAttempt).filter_by(scheduled_notification_id=row.id, push_token_id=tokens[0].id).one()
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(NotificationDeliveryAttempt(scheduled_notification_id=row.id, user_id=identity["user"]["id"], channel="push", push_token_id=tokens[0].id, attempt_number=attempt.attempt_number))
        db_session.flush()


def test_detach_is_installation_scoped_and_rotation_retires_previous_token(client, db_session, monkeypatch):
    identity, league, tokens = seed(client, db_session, monkeypatch)
    headers = auth_headers(identity["access_token"])
    device = {"account_id": identity["user"]["id"], "installation_id": str(uuid4()), "installation_secret": "a" * 64, "app_id": "test-app", "platform": "ios", "environment": "development"}
    first = client.post("/notifications/tokens", json={**device, "subscription_id": "rotating-first"}, headers=headers)
    assert first.status_code == 200
    rotated = client.post("/notifications/tokens", json={**device, "subscription_id": "rotating-second"}, headers=headers)
    assert rotated.status_code == 200
    db_session.expire_all()
    assert not db_session.get(PushToken, first.json()["id"]).enabled
    assert client.post("/notifications/tokens/detach", json={**device}, headers=headers).json() == {"disabled": 1}
    db_session.expire_all()
    assert all(db_session.get(PushToken, token.id).enabled for token in tokens)
    assert client.post("/notifications/tokens/detach", json={}, headers=headers).json() == {"disabled": 0}


def test_account_switch_requires_installation_capability_and_authenticated_actor(client, db_session, monkeypatch):
    first, league, tokens = seed(client, db_session, monkeypatch)
    second = create_user(client, "native-switch")
    device = {"account_id": first["user"]["id"], "installation_id": str(uuid4()), "installation_secret": "a" * 64, "app_id": "test-app", "platform": "ios", "environment": "development", "subscription_id": "shared-phone"}
    assert client.post("/notifications/tokens", json=device, headers=auth_headers(first["access_token"])).status_code == 200
    other_headers = auth_headers(second["access_token"])
    assert client.post("/notifications/tokens", json=device, headers=other_headers).status_code == 404
    device["account_id"] = second["user"]["id"]
    assert client.post("/notifications/tokens", json={**device, "installation_secret": "b" * 64}, headers=other_headers).status_code == 404
    assert client.post("/notifications/tokens", json=device, headers=other_headers).status_code == 200
    db_session.expire_all()
    active = db_session.query(PushToken).filter_by(device_token="shared-phone", enabled=True).one()
    assert active.user_id == second["user"]["id"]


@pytest.mark.parametrize("event_type,field", [("DRAFT_START", "push_drafts"), ("MATCHUP_START", "push_matchups"), ("INJURY", "push_injuries")])
def test_phone_categories_are_independent_of_email_preferences(client, db_session, monkeypatch, event_type, field):
    from collegefootballfantasy_api.app.services.notification_service import _phone_category_allowed
    identity, league, tokens = seed(client, db_session, monkeypatch)
    user_id = identity["user"]["id"]
    prefs = NotificationPreference(user_id=user_id, user_key=str(user_id), email_enabled=True)
    setattr(prefs, field, False)
    db_session.add(prefs); db_session.commit()
    assert not _phone_category_allowed(event_type, prefs)
    payload = client.get("/notifications/preferences", headers=auth_headers(identity["access_token"])).json()
    assert payload[field] is False and payload["email_enabled"] is True
    # An older client saving an unrelated preference cannot undo phone choices.
    client.post("/notifications/preferences", json={"email_enabled": True}, headers=auth_headers(identity["access_token"]))
    db_session.refresh(prefs)
    assert getattr(prefs, field) is False


def test_canceled_draft_and_expired_event_never_dispatch(client, db_session, monkeypatch):
    identity, league, tokens = seed(client, db_session, monkeypatch)
    draft = db_session.query(Draft).filter_by(league_id=league["id"]).one()
    draft.status = "canceled"; db_session.commit()
    canceled = event(db_session, identity, league, event_type="DRAFT_START", payload={"draft_id": draft.id})
    expired = event(db_session, identity, league, scheduled_for=datetime.now(timezone.utc)-timedelta(days=10))
    provider = FakePushProvider(); dispatch(db_session, provider)
    assert not provider.messages
    db_session.refresh(canceled); db_session.refresh(expired)
    assert canceled.status == "canceled" and expired.status == "expired"


def test_live_draft_start_queues_once_and_detached_device_is_suppressed(client, db_session, monkeypatch):
    from collegefootballfantasy_api.app.services.draft_service import _notify_draft_start
    from collegefootballfantasy_api.app.models.league import League
    identity, league, tokens = seed(client, db_session, monkeypatch)
    draft = db_session.query(Draft).filter_by(league_id=league["id"]).one(); draft.status="on_clock"
    _notify_draft_start(db_session, league=db_session.get(League, league["id"]), draft_row=draft)
    _notify_draft_start(db_session, league=db_session.get(League, league["id"]), draft_row=draft)
    tokens[0].enabled = False; db_session.commit()
    provider = FakePushProvider(); dispatch(db_session, provider)
    assert len(provider.messages) == 1
    assert provider.messages[0]["data"]["destination"]["league_id"] == league["id"]
    assert db_session.query(ScheduledNotification).filter_by(event_type="DRAFT_START").count() == 1


def test_transient_retry_targets_only_failed_device_and_keeps_provider_idempotency(client, db_session, monkeypatch):
    identity, league, tokens = seed(client, db_session, monkeypatch)
    row = event(db_session, identity, league)
    class Provider:
        calls = []
        def send(self, **payload):
            self.calls.append(payload)
            if payload["subscription_id"] == "phone-0" and len(self.calls) == 1:
                return ProviderDeliveryResult(accepted=False, retryable=True, error="temporary")
            return ProviderDeliveryResult(accepted=True, provider_message_id="accepted")
    provider=Provider(); now=datetime.now(timezone.utc)
    dispatch(db_session, provider, now=now)
    dispatch(db_session, provider, now=now+timedelta(minutes=2))
    assert [p["subscription_id"] for p in provider.calls] == ["phone-0", "phone-1", "phone-0"]
    assert provider.calls[0]["idempotency_key"] == provider.calls[-1]["idempotency_key"]
    assert row.status == "provider_accepted"


def test_invalid_subscription_only_disables_that_device_and_never_retries(client, db_session, monkeypatch):
    identity, league, tokens = seed(client, db_session, monkeypatch)
    row=event(db_session, identity, league)
    class Provider(FakePushProvider):
        def send(self, **payload):
            if payload["subscription_id"] == "phone-0":
                self.messages.append(payload)
                return ProviderDeliveryResult(accepted=False, invalid_subscription_id="phone-0", error="invalid")
            return super().send(**payload)
    provider=Provider(); dispatch(db_session, provider); dispatch(db_session, provider)
    db_session.refresh(tokens[0]); db_session.refresh(tokens[1])
    assert not tokens[0].enabled and tokens[1].enabled
    assert len(provider.messages) == 2
    assert db_session.query(NotificationDeliveryAttempt).filter_by(scheduled_notification_id=row.id, push_token_id=tokens[0].id).one().status == "invalid_token"


@pytest.mark.parametrize("slot", ["QB", "BENCH", "IR"])
def test_injury_baseline_unchanged_probable_and_dropped_player_are_safe(client, db_session, monkeypatch, slot):
    identity, league, tokens = seed(client, db_session, monkeypatch)
    team=db_session.query(Team).filter_by(league_id=league["id"], owner_user_id=identity["user"]["id"]).one()
    player=Player(name="Verified Player", school="Auburn", position="QB"); db_session.add(player); db_session.flush()
    roster=RosterEntry(team_id=team.id, league_id=league["id"], player_id=player.id, slot=slot, status="active")
    db_session.add(roster); db_session.commit()
    def ingest(status, notes="dated official report"):
        _upsert_official_availability_rows(db_session, season=2026, week=6, rows=[{"player_name": player.name, "team_name": "Auburn", "position": "QB", "conference": "SEC", "status": status, "notes": notes, "source_url": "https://www.secsports.com/fbreports"}]); db_session.commit()
    ingest("Probable")
    assert db_session.query(ScheduledNotification).filter_by(event_type="INJURY").count() == 0
    ingest("Questionable"); ingest("Questionable", "updated notes only")
    assert db_session.query(ScheduledNotification).filter_by(event_type="INJURY").count() == 1
    ingest("Doubtful")
    assert db_session.query(ScheduledNotification).filter_by(event_type="INJURY").count() == 2
    db_session.delete(roster); db_session.commit()
    provider=FakePushProvider(); dispatch(db_session, provider)
    assert not provider.messages


def test_initial_out_snapshot_is_baseline_not_a_mass_injury_alert(client, db_session, monkeypatch):
    identity, league, tokens=seed(client, db_session, monkeypatch)
    player=Player(name="First Snapshot", school="Texas", position="RB"); db_session.add(player); db_session.flush()
    team=db_session.query(Team).filter_by(league_id=league["id"], owner_user_id=identity["user"]["id"]).one()
    db_session.add(RosterEntry(team_id=team.id, league_id=league["id"], player_id=player.id, slot="BENCH", status="active")); db_session.commit()
    _upsert_official_availability_rows(db_session, season=2026, week=6, rows=[{"player_name": player.name, "team_name": "Texas", "status": "Out", "conference": "SEC"}]); db_session.commit()
    assert db_session.query(ScheduledNotification).filter_by(event_type="INJURY").count() == 0


def test_admin_news_requires_preview_confirmation_optin_and_delivery_recheck(client, db_session, monkeypatch):
    identity, league, tokens=seed(client, db_session, monkeypatch)
    admin=create_user(client,"news-admin"); db_session.get(User, admin["user"]["id"]).is_admin=True
    prefs=NotificationPreference(user_id=identity["user"]["id"],user_key=str(identity["user"]["id"]), push_major_news=True)
    db_session.add(prefs); db_session.commit()
    admin_headers=auth_headers(admin["access_token"]); user_headers=auth_headers(identity["access_token"])
    assert client.post("/notifications/announcements/admin",json={"title":"News","body":"Verified news"},headers=user_headers).status_code == 403
    created=client.post("/notifications/announcements/admin",json={"title":"News","body":"Verified news"},headers=admin_headers).json()
    assert db_session.query(ScheduledNotification).filter_by(event_type="MAJOR_NEWS").count()==0
    preview=client.get(f'/notifications/announcements/admin/{created["id"]}/preview',headers=admin_headers).json()
    assert preview["recipient_count"]==1
    assert client.post(f'/notifications/announcements/admin/{created["id"]}/confirm',json={"confirm":False},headers=admin_headers).status_code==422
    for _ in range(2):
        assert client.post(f'/notifications/announcements/admin/{created["id"]}/confirm',json={"confirm":True},headers=admin_headers).status_code==200
    assert db_session.query(ScheduledNotification).filter_by(event_type="MAJOR_NEWS").count()==1
    assert client.get(f'/notifications/announcements/{created["id"]}',headers=user_headers).status_code==200
    prefs.push_major_news=False; db_session.commit()
    provider=FakePushProvider(); dispatch(db_session,provider)
    assert not provider.messages


def test_tap_destination_is_account_and_current_membership_scoped(client, db_session, monkeypatch):
    from collegefootballfantasy_api.app.models.league_member import LeagueMember
    identity, league, tokens=seed(client,db_session,monkeypatch)
    row=event(db_session,identity,league,payload={"trade_id":12})
    headers=auth_headers(identity["access_token"])
    assert client.get(f"/notifications/events/{row.id}/open",headers=headers).json()["allowed"]
    other=create_user(client,"tap-foreign")
    assert client.get(f"/notifications/events/{row.id}/open",headers=auth_headers(other["access_token"])).status_code==404
    db_session.query(LeagueMember).filter_by(league_id=league["id"],user_id=identity["user"]["id"]).delete();db_session.commit()
    assert not client.get(f"/notifications/events/{row.id}/open",headers=headers).json()["allowed"]


def test_provider_verifies_identity_and_rejects_foreign_subscription(monkeypatch):
    from collegefootballfantasy_api.app.services import notification_providers
    monkeypatch.setattr(settings,"onesignal_app_id","app-id")
    monkeypatch.setattr(notification_providers.httpx,"get",lambda *_a,**_k:httpx.Response(200,json={"identity":{"external_id":"cfb_user:1"}}))
    verify_subscription_identity("private-subscription","cfb_user:1")
    with pytest.raises(PermissionError):verify_subscription_identity("private-subscription","cfb_user:2")


def test_provider_requires_message_id_uses_visible_alert_and_exact_subscription(monkeypatch):
    from collegefootballfantasy_api.app.services import notification_providers
    monkeypatch.setattr(settings,"onesignal_app_id","app-id");monkeypatch.setattr(settings,"onesignal_app_api_key","key")
    captured={}
    def post(*_a,**kwargs):captured.update(kwargs);return httpx.Response(200,json={"id":"accepted-id"})
    monkeypatch.setattr(notification_providers.httpx,"post",post)
    result=OneSignalPushProvider().send(external_user_id="cfb_user:1",subscription_id="only-this-phone",title="Title",body="Body",data={},idempotency_key="stable",ttl=60,badge_count=3)
    assert result.accepted
    payload=captured["json"]
    assert payload["include_subscription_ids"]==["only-this-phone"] and "include_aliases" not in payload
    assert payload["contents"]=={"en":"Body"} and not payload.get("content_available")
    assert payload["ttl"]==60 and payload["ios_badgeCount"]==3
    monkeypatch.setattr(notification_providers.httpx,"post",lambda *_a,**_k:httpx.Response(200,json={"id":"","errors":{"invalid_player_ids":["only-this-phone"]}}))
    invalid=OneSignalPushProvider().send(external_user_id="cfb_user:1",subscription_id="only-this-phone",title="Title",body="Body",data={},idempotency_key="stable")
    assert not invalid.accepted and invalid.invalid_subscription_id=="only-this-phone"


@pytest.mark.parametrize("disabled", [False, True])
def test_injury_combines_leagues_and_rechecks_remaining_ownership(client, db_session, monkeypatch, disabled):
    from collegefootballfantasy_api.app.models.league_member import LeagueMember
    identity, first, _ = seed(client, db_session, monkeypatch)
    second = create_league(client, identity["access_token"], "Second injury league")
    player = Player(name="Combined Receiver", school="Auburn", position="WR")
    db_session.add(player); db_session.flush()
    for league in [first, second]:
        team = db_session.query(Team).filter_by(league_id=league["id"], owner_user_id=identity["user"]["id"]).one()
        db_session.add(RosterEntry(team_id=team.id, league_id=league["id"], player_id=player.id, slot="IR", status="active"))
    db_session.commit()
    for status in ["Available", "Doubtful"]:
        _upsert_official_availability_rows(db_session, season=2026, week=6, rows=[{"player_name": player.name, "team_name": player.school, "position": "WR", "conference": "SEC", "status": status}])
        db_session.commit()
    row = db_session.query(ScheduledNotification).filter_by(event_type="INJURY").one()
    db_session.query(LeagueMember).filter_by(league_id=first["id"], user_id=identity["user"]["id"]).delete()
    db_session.commit()
    if disabled:
        db_session.add(NotificationPreference(user_id=identity["user"]["id"], user_key=str(identity["user"]["id"]), push_injuries=False)); db_session.commit()
    provider = FakePushProvider(); dispatch(db_session, provider)
    assert len(provider.messages) == (0 if disabled else 2)  # One event, one delivery per current phone.
    assert all(message["data"]["destination"]["league_id"] == second["id"] for message in provider.messages)
    assert all("Doubtful" in message["body"] for message in provider.messages)
    assert client.get(f"/notifications/events/{row.id}/open", headers=auth_headers(identity["access_token"])).json()["allowed"]


@pytest.mark.parametrize("disabled", [False, True])
def test_matchup_start_dispatch_reschedule_category_and_missing_content(client, db_session, monkeypatch, disabled):
    from collegefootballfantasy_api.app.models.matchup import Matchup
    from collegefootballfantasy_api.app.models.lineup_week_snapshot import LineupWeekSnapshot
    from collegefootballfantasy_api.app.services.notification_service import rebuild_matchup_start_notifications
    identity, league, _ = seed(client, db_session, monkeypatch)
    team = db_session.query(Team).filter_by(league_id=league["id"], owner_user_id=identity["user"]["id"]).one()
    player = Player(name="Matchup Receiver", school="Texas", position="WR")
    db_session.add(player); db_session.flush()
    now = datetime.now(timezone.utc)
    matchup = Matchup(league_id=league["id"], season=2026, week=6, home_team_id=team.id, away_team_id=team.id)
    snapshot = LineupWeekSnapshot(league_id=league["id"], team_id=team.id, player_id=player.id, season=2026, week=6, slot="WR", is_starter=True, game_start_at=now)
    db_session.add_all([matchup, snapshot, RosterEntry(league_id=league["id"], team_id=team.id, player_id=player.id, slot="WR", status="active")]); db_session.commit()
    rebuild_matchup_start_notifications(db_session, league_id=league["id"], season=2026, week=6); db_session.commit()
    snapshot.game_start_at = now + timedelta(hours=1); db_session.commit()
    rebuild_matchup_start_notifications(db_session, league_id=league["id"], season=2026, week=6); db_session.commit()
    if disabled:
        db_session.add(NotificationPreference(user_id=identity["user"]["id"], user_key=str(identity["user"]["id"]), push_matchups=False)); db_session.commit()
    provider = FakePushProvider(); dispatch(db_session, provider, now=now+timedelta(minutes=1))
    assert not provider.messages
    dispatch(db_session, provider, now=now+timedelta(hours=1, seconds=1)); dispatch(db_session, provider, now=now+timedelta(hours=1, seconds=2))
    messages = [message for message in provider.messages if message["data"]["event_type"] == "MATCHUP_START"]
    assert len(messages) == (0 if disabled else 2)
    destination = messages[0]["data"]["destination"] if messages else db_session.query(ScheduledNotification).filter_by(event_type="MATCHUP_START").one().payload["destination"]
    assert destination["resource_id"] == matchup.id and destination["week"] == 6
    row = db_session.query(ScheduledNotification).filter_by(event_type="MATCHUP_START").one()
    db_session.delete(matchup); db_session.commit()
    assert not client.get(f"/notifications/events/{row.id}/open", headers=auth_headers(identity["access_token"])).json()["allowed"]


def test_disabled_draft_phone_category_keeps_email_delivery(client, db_session, monkeypatch):
    identity, league, _ = seed(client, db_session, monkeypatch)
    monkeypatch.setattr(settings, "email_enabled", True)
    draft = db_session.query(Draft).filter_by(league_id=league["id"]).one()
    draft.status = "on_clock"
    db_session.add(NotificationPreference(user_id=identity["user"]["id"], user_key=str(identity["user"]["id"]), push_drafts=False, email_enabled=True))
    db_session.commit()
    queue_notification_event(db_session, league_id=league["id"], user_id=identity["user"]["id"], event_type="DRAFT_START", event_key="disabled-category", payload={"draft_id": draft.id}, channels=("in_app", "push", "email")); db_session.commit()
    push, email = FakePushProvider(), FakeEmailProvider()
    process_due_notifications_once(db_session, push_provider=push, email_provider=email)
    assert not push.messages and len(email.messages) == 1


def test_concurrent_workers_cannot_duplicate_device_dispatch(client, db_session, monkeypatch):
    if db_session.bind.dialect.name != "postgresql":
        pytest.skip("Requires isolated PostgreSQL row-lock verification")
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier, Lock
    from sqlalchemy.orm import Session
    identity, league, _ = seed(client, db_session, monkeypatch)
    row = event(db_session, identity, league)
    barrier, lock = Barrier(2), Lock()
    provider = FakePushProvider()
    original = provider.send
    def send(**kwargs):
        with lock:
            return original(**kwargs)
    provider.send = send
    def worker(index):
        with Session(db_session.bind) as session:
            barrier.wait(timeout=5)
            return dispatch(session, provider, worker_id=f"concurrent-{index}")
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(worker, range(2)))
    assert sum(result["claimed"] for result in results) == 1
    assert len(provider.messages) == 2
    db_session.expire_all()
    assert db_session.get(ScheduledNotification, row.id).status == "provider_accepted"


def test_confirmed_major_news_delivers_only_opted_in_users_current_devices(client, db_session, monkeypatch):
    from collegefootballfantasy_api.app.services.notification_service import create_news_announcement, confirm_news_announcement
    from collegefootballfantasy_api.app.schemas.notification import NewsAnnouncementCreate
    identity, _, _ = seed(client, db_session, monkeypatch)
    not_opted_in = create_user(client, "news-no-optin")
    db_session.add(PushToken(user_id=not_opted_in["user"]["id"], user_key=str(not_opted_in["user"]["id"]), device_token="not-eligible", provider="onesignal", platform="ios"))
    db_session.add(NotificationPreference(user_id=identity["user"]["id"], user_key=str(identity["user"]["id"]), push_major_news=True)); db_session.commit()
    news = create_news_announcement(db_session, identity["user"]["id"], NewsAnnouncementCreate(title="Verified news", body="An approved isolated announcement"))
    confirm_news_announcement(db_session, news["id"])
    provider = FakePushProvider(); dispatch(db_session, provider); dispatch(db_session, provider)
    assert len(provider.messages) == 2
    assert {message["subscription_id"] for message in provider.messages} == {"phone-0", "phone-1"}
    assert all(message["data"]["destination"] == {"type": "announcement", "league_id": None, "resource_id": news["id"]} for message in provider.messages)


def test_native_provider_fallback_never_displays_private_roster_content(monkeypatch):
    from collegefootballfantasy_api.app.services import notification_providers
    monkeypatch.setattr(settings, "onesignal_app_id", "app")
    monkeypatch.setattr(settings, "onesignal_app_api_key", "test-only")
    captured = {}
    def post(*args, **kwargs):
        captured.update(kwargs["json"])
        return httpx.Response(200, json={"id": "accepted"})
    monkeypatch.setattr(notification_providers.httpx, "post", post)
    result = OneSignalPushProvider().send(external_user_id="cfb_user:7", subscription_id="phone", private_alert=True, title="Private league draft", body="Your rostered receiver is doubtful", data={"recipient_user_id": 7, "expires_at": 200}, idempotency_key="stable")
    assert result.accepted
    assert captured["headings"] == {"en": "CFFB"}
    assert captured["contents"] == {"en": "Open CFFB to view your alert."}
    assert captured["data"]["alert_title"] == "Private league draft"
    assert captured["data"]["recipient_user_id"] == 7
    assert captured["mutable_content"] is True


def test_existing_phone_categories_outside_the_new_four_still_apply():
    from collegefootballfantasy_api.app.services.notification_service import _phone_category_allowed
    prefs = NotificationPreference(user_id=1, user_key="1", trade_alerts=False)
    assert not _phone_category_allowed("TRADE_PROPOSED", prefs)


def test_device_delivery_expires_during_a_slow_provider_batch(client, db_session, monkeypatch):
    from collegefootballfantasy_api.app.services import notification_service
    identity, league, _ = seed(client, db_session, monkeypatch)
    now = datetime.now(timezone.utc)
    row = event(db_session, identity, league, scheduled_for=now)
    row.expires_at = now + timedelta(seconds=60); db_session.commit()
    clock = {"now": now}
    monkeypatch.setattr(notification_service, "utcnow", lambda: clock["now"])
    class SlowProvider(FakePushProvider):
        def send(self, **payload):
            result = super().send(**payload)
            clock["now"] += timedelta(seconds=61)
            return result
    provider = SlowProvider(); dispatch(db_session, provider)
    assert len(provider.messages) == 1
    db_session.refresh(row)
    assert row.status == "expired"
    assert db_session.query(NotificationDeliveryAttempt).filter_by(scheduled_notification_id=row.id, status="expired").count() == 1
