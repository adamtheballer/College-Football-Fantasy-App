from datetime import datetime, timezone

from conftest import TestingSessionLocal

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.domain.permissions import PermissionAction, PermissionContext, can
from collegefootballfantasy_api.app.models.audit_event import AuditEvent
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.user import User


STRONG_PASSWORD = "StrongPass123!"


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def signup_user(client, suffix: str, *, verified: bool = True) -> tuple[int, str]:
    email = f"authz-{suffix}@example.com"
    response = client.post(
        "/auth/signup",
        json={"first_name": f"Authz{suffix}", "email": email, "password": STRONG_PASSWORD},
    )
    assert response.status_code == 201
    with TestingSessionLocal() as session:
        user = session.query(User).filter(User.email == email).one()
        if verified:
            user.email_verified_at = datetime.now(timezone.utc)
        session.commit()
        user_id = user.id
    return user_id, response.json()["access_token"]


def league_payload(name: str = "Authorization League") -> dict:
    return {
        "basics": {
            "name": name,
            "season_year": 2026,
            "max_teams": 4,
            "is_private": True,
            "description": "Authorization matrix league",
            "icon_url": None,
        },
        "settings": {
            "scoring_json": {"ppr": 1},
            "roster_slots_json": {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "BENCH": 4, "IR": 1},
            "playoff_teams": 2,
            "waiver_type": "faab",
            "trade_review_type": "commissioner",
            "superflex_enabled": False,
            "kicker_enabled": True,
            "defense_enabled": False,
        },
        "draft": {
            "draft_datetime_utc": "2026-08-19T18:00:00Z",
            "timezone": "America/New_York",
            "draft_type": "snake",
            "pick_timer_seconds": 90,
        },
    }


def create_league(client, token: str, name: str = "Authorization League") -> dict:
    response = client.post("/leagues", json=league_payload(name), headers=auth_headers(token))
    assert response.status_code == 201
    return response.json()["league"]


def create_player(client, suffix: str = "one") -> int:
    response = client.post(
        "/players",
        json=[
            {
                "external_id": None,
                "name": f"Authz Player {suffix}",
                "position": "RB",
                "school": "Texas",
                "image_url": None,
            }
        ],
    )
    assert response.status_code == 201
    return response.json()[0]["id"]


def settings_update_payload() -> dict:
    return {
        "scoring_json": {"ppr": 0.5},
        "roster_slots_json": {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "BENCH": 4, "IR": 1},
        "playoff_teams": 2,
        "waiver_type": "faab",
        "trade_review_type": "commissioner",
        "superflex_enabled": False,
        "kicker_enabled": True,
        "defense_enabled": False,
    }


def test_permission_domain_matrix_roles_and_actions():
    anonymous = PermissionContext(authenticated=False, verified=False)
    unverified = PermissionContext(authenticated=True, verified=False)
    verified = PermissionContext(authenticated=True, verified=True)
    member = PermissionContext(authenticated=True, verified=True, league_member=True)
    owner = PermissionContext(authenticated=True, verified=True, league_member=True, team_owner=True)
    commissioner = PermissionContext(authenticated=True, verified=True, league_member=True, commissioner=True)
    admin = PermissionContext(authenticated=True, verified=True, admin=True)

    assert not can(anonymous, PermissionAction.READ_LEAGUE)
    assert not can(unverified, PermissionAction.CREATE_LEAGUE)
    assert can(verified, PermissionAction.CREATE_LEAGUE)
    assert can(member, PermissionAction.READ_LEAGUE)
    assert not can(member, PermissionAction.UPDATE_LEAGUE)
    assert can(owner, PermissionAction.ROSTER_MOVE)
    assert not can(owner, PermissionAction.SCORE_RECALC)
    assert can(commissioner, PermissionAction.SCORE_RECALC)
    assert can(admin, PermissionAction.REMOVE_MEMBER)


def test_non_member_cannot_read_private_league(client):
    _commissioner_id, commissioner_token = signup_user(client, "private-owner")
    _outsider_id, outsider_token = signup_user(client, "private-outsider")
    league = create_league(client, commissioner_token, "Private Authz League")

    response = client.get(f"/leagues/{league['id']}", headers=auth_headers(outsider_token))

    assert response.status_code == 403
    assert response.json()["detail"] == "league membership required"


def test_member_cannot_edit_league_settings(client):
    _commissioner_id, commissioner_token = signup_user(client, "settings-owner")
    _member_id, member_token = signup_user(client, "settings-member")
    league = create_league(client, commissioner_token, "Settings Authz League")
    assert client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token)).status_code == 200

    response = client.patch(
        f"/leagues/{league['id']}/settings",
        json=settings_update_payload(),
        headers=auth_headers(member_token),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "commissioner only"


def test_team_owner_cannot_mutate_another_roster(client, db_session):
    _commissioner_id, commissioner_token = signup_user(client, "roster-owner")
    _member_id, member_token = signup_user(client, "roster-member")
    league = create_league(client, commissioner_token, "Roster Authz League")
    assert client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token)).status_code == 200
    commissioner_team = (
        db_session.query(Team)
        .filter(Team.league_id == league["id"], Team.owner_name == "Authzroster-owner")
        .one()
    )
    player_id = create_player(client, "roster")

    response = client.post(
        f"/teams/{commissioner_team.id}/roster",
        json={"player_id": player_id, "slot": "RB", "status": "active"},
        headers=auth_headers(member_token),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "team ownership required"


def test_commissioner_override_roster_move_creates_audit_event(client, db_session):
    _commissioner_id, commissioner_token = signup_user(client, "override-owner")
    _member_id, member_token = signup_user(client, "override-member")
    league = create_league(client, commissioner_token, "Override Authz League")
    assert client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token)).status_code == 200
    member_team = (
        db_session.query(Team)
        .filter(Team.league_id == league["id"], Team.owner_name == "Authzoverride-member")
        .one()
    )
    player_id = create_player(client, "override")

    response = client.post(
        f"/teams/{member_team.id}/roster",
        json={"player_id": player_id, "slot": "RB", "status": "active"},
        headers=auth_headers(commissioner_token),
    )

    assert response.status_code == 201
    audit = db_session.query(AuditEvent).filter(AuditEvent.action == "roster.add").one()
    assert audit.actor_user_id == league["commissioner_user_id"]
    assert audit.team_id == member_team.id


def test_unverified_user_cannot_create_league_when_verification_required(client):
    original = settings.auth_require_email_verification
    settings.auth_require_email_verification = True
    try:
        _user_id, token = signup_user(client, "unverified", verified=False)
        response = client.post("/leagues", json=league_payload("Unverified League"), headers=auth_headers(token))
    finally:
        settings.auth_require_email_verification = original

    assert response.status_code == 403
    assert response.json()["detail"] == "email verification required"
