from datetime import datetime, timedelta, timezone

from conftest import TestingSessionLocal

from collegefootballfantasy_api.app.models.audit_event import AuditEvent
from collegefootballfantasy_api.app.models.user import User


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_user_and_token(client, suffix: str) -> str:
    email = f"audit-{suffix}@example.com"
    response = client.post(
        "/auth/signup",
        json={
            "first_name": f"Audit{suffix}",
            "email": email,
            "password": "StrongPass123!",
        },
    )
    assert response.status_code == 201
    with TestingSessionLocal() as session:
        user = session.query(User).filter(User.email == email).one()
        user.email_verified_at = datetime.now(timezone.utc)
        session.commit()
    return response.json()["access_token"]


def league_payload(name: str = "Audit League", max_teams: int = 2) -> dict:
    return {
        "basics": {
            "name": name,
            "season_year": 2026,
            "max_teams": max_teams,
            "is_private": True,
            "description": "Audit test league",
            "icon_url": None,
        },
        "settings": {
            "scoring_json": {"ppr": 1},
            "roster_slots_json": {"QB": 1},
            "playoff_teams": 4,
            "waiver_type": "faab",
            "trade_review_type": "commissioner",
            "superflex_enabled": False,
            "kicker_enabled": False,
            "defense_enabled": False,
        },
        "draft": {
            "draft_datetime_utc": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
            "timezone": "America/Los_Angeles",
            "draft_type": "snake",
            "pick_timer_seconds": 90,
        },
    }


def create_league(client, token: str, *, name: str = "Audit League", max_teams: int = 2) -> dict:
    response = client.post(
        "/leagues",
        json=league_payload(name=name, max_teams=max_teams),
        headers=auth_headers(token),
    )
    assert response.status_code == 201
    return response.json()["league"]


def audit_events(action: str) -> list[AuditEvent]:
    with TestingSessionLocal() as session:
        return (
            session.query(AuditEvent)
            .filter(AuditEvent.action == action)
            .order_by(AuditEvent.id.asc())
            .all()
        )


def test_create_league_records_audit_event(client):
    token = create_user_and_token(client, "create")
    league = create_league(client, token, name="Audited Create")

    events = audit_events("league.create")
    assert len(events) == 1
    event = events[0]
    assert event.league_id == league["id"]
    assert event.entity_type == "league"
    assert event.entity_id == str(league["id"])
    assert event.after_json["league"]["name"] == "Audited Create"
    assert event.after_json["settings"]["roster_slots_json"]["QB"] == 1


def test_join_league_records_audit_event(client):
    owner_token = create_user_and_token(client, "owner")
    league = create_league(client, owner_token, name="Audited Join")
    member_token = create_user_and_token(client, "member")

    response = client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token))

    assert response.status_code == 200
    events = audit_events("league.join")
    assert len(events) == 1
    assert events[0].league_id == league["id"]
    assert events[0].after_json["member_count"] == 2


def test_update_league_settings_records_before_and_after(client):
    token = create_user_and_token(client, "settings")
    league = create_league(client, token, name="Audited Settings")
    payload = {
        "scoring_json": {"ppr": 0.5, "pass_td": 6},
        "roster_slots_json": {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "K": 1, "BENCH": 6, "IR": 1},
        "playoff_teams": 2,
        "waiver_type": "rolling",
        "trade_review_type": "commissioner",
        "superflex_enabled": False,
        "kicker_enabled": True,
        "defense_enabled": False,
    }

    response = client.patch(f"/leagues/{league['id']}/settings", json=payload, headers=auth_headers(token))

    assert response.status_code == 200
    events = audit_events("league.settings.update")
    assert len(events) == 1
    assert events[0].league_id == league["id"]
    assert events[0].before_json["scoring_json"] == {"ppr": 1}
    assert events[0].after_json["scoring_json"] == {"ppr": 0.5, "pass_td": 6}
    assert events[0].after_json["roster_slots_json"]["K"] == 1


def test_real_draft_pick_records_audit_event(client):
    owner_token = create_user_and_token(client, "draft-owner")
    league = create_league(client, owner_token, name="Audited Draft")
    join_token = create_user_and_token(client, "draft-member")
    join_response = client.post(f"/leagues/{league['id']}/join", headers=auth_headers(join_token))
    assert join_response.status_code == 200
    player_response = client.post(
        "/players",
        json=[{"external_id": None, "name": "Audit QB", "position": "QB", "school": "Texas", "image_url": None}],
    )
    assert player_response.status_code == 201
    player_id = player_response.json()[0]["id"]

    pick_response = client.post(
        f"/leagues/{league['id']}/draft-picks",
        json={"player_id": player_id},
        headers=auth_headers(owner_token),
    )

    assert pick_response.status_code == 201
    events = audit_events("draft.pick.create")
    assert len(events) == 1
    assert events[0].league_id == league["id"]
    assert events[0].after_json["player_id"] == player_id
    assert events[0].after_json["overall_pick"] == 1
    assert events[0].after_json["assigned_slot"] == "QB"
