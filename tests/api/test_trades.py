import pytest
from datetime import datetime, timedelta, timezone

from conftest import TestingSessionLocal

from collegefootballfantasy_api.app.api.routes.trades import (
    DEFAULT_ROSTER_SLOTS,
    _normalize_roster_slots,
)
from collegefootballfantasy_api.app.models.audit_event import AuditEvent
from collegefootballfantasy_api.app.models.notification import NotificationLog
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.transaction import Transaction
from collegefootballfantasy_api.app.models.user import User


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_user_and_token(client, suffix: str = "trade") -> str:
    email = f"coach-{suffix}@example.com"
    response = client.post(
        "/auth/signup",
        json={
            "first_name": f"Coach{suffix}",
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


def create_league(client, token: str, fill_league: bool = False) -> dict:
    response = client.post(
        "/leagues",
        json={
            "basics": {
                "name": "Trade League",
                "season_year": 2026,
                "max_teams": 2,
                "is_private": True,
                "description": None,
                "icon_url": None,
            },
            "settings": {
                "scoring_json": {"ppr": 1},
                "roster_slots_json": {"QB": 1, "RB": 1, "WR": 1, "TE": 1, "K": 1, "BENCH": 4},
                "playoff_teams": 2,
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
        },
        headers=auth_headers(token),
    )
    assert response.status_code == 201
    league = response.json()["league"]
    if fill_league:
        member_token = create_user_and_token(client, f"member-{league['id']}")
        join_response = client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token))
        assert join_response.status_code == 200
        league["member_token"] = member_token
    return league


def create_trade_players(db_session, league_id: int) -> tuple[Team, Team, Player, Player]:
    teams = db_session.query(Team).filter(Team.league_id == league_id).order_by(Team.id.asc()).all()
    assert len(teams) == 2
    first_team, second_team = teams
    first_player = Player(name="Trade RB", position="RB", school="Texas")
    second_player = Player(name="Trade WR", position="WR", school="Oregon")
    db_session.add_all([first_player, second_player])
    db_session.flush()
    db_session.add_all(
        [
            RosterEntry(
                league_id=league_id,
                team_id=first_team.id,
                player_id=first_player.id,
                slot="RB",
                status="active",
            ),
            RosterEntry(
                league_id=league_id,
                team_id=second_team.id,
                player_id=second_player.id,
                slot="WR",
                status="active",
            ),
        ]
    )
    db_session.commit()
    return first_team, second_team, first_player, second_player


def trade_offer_payload(first_team: Team, second_team: Team, first_player: Player, second_player: Player) -> dict:
    return {
        "proposing_team_id": first_team.id,
        "receiving_team_id": second_team.id,
        "proposing_items": [{"player_id": first_player.id}],
        "receiving_items": [{"player_id": second_player.id}],
        "message": "Swap starters",
    }


def trade_payload() -> dict:
    return {
        "receive_ids": [1],
        "give_ids": [2],
        "season": 2026,
        "week": 1,
        "league_size": 12,
        "roster_slots": {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "BE": 4, "IR": 1},
    }


def test_trade_analyze_requires_auth(client):
    response = client.post("/trade/analyze", json=trade_payload())

    assert response.status_code == 401
    assert response.json()["detail"] == "missing auth token"


def test_trade_analyze_allows_authenticated_user(client):
    token = create_user_and_token(client)

    response = client.post(
        "/trade/analyze",
        json=trade_payload(),
        headers=auth_headers(token),
    )

    assert response.status_code == 200


def test_normalize_roster_slots_uses_payload_values():
    slots = _normalize_roster_slots(
        {
            "QB": 2,
            "RB": 1,
            "WR": 3,
            "TE": 2,
            "K": 0,
            "BE": 8,
            "IR": 2,
        }
    )

    assert slots == {
        "QB": 2,
        "RB": 1,
        "WR": 3,
        "TE": 2,
        "K": 0,
        "BE": 8,
        "IR": 2,
    }


def test_normalize_roster_slots_accepts_bench_alias():
    slots = _normalize_roster_slots({"BENCH": 6})

    assert slots["BE"] == 6


def test_normalize_roster_slots_preserves_defaults_for_missing_values():
    slots = _normalize_roster_slots({"QB": 2})

    assert slots["QB"] == 2
    assert slots["RB"] == DEFAULT_ROSTER_SLOTS["RB"]
    assert slots["BE"] == DEFAULT_ROSTER_SLOTS["BE"]


def test_normalize_roster_slots_rejects_non_numeric_values():
    with pytest.raises((TypeError, ValueError)):
        _normalize_roster_slots({"QB": "bad"})  # type: ignore[dict-item]


def test_trade_offer_accept_approve_processes_atomic_roster_swap(client, db_session):
    owner_token = create_user_and_token(client, "owner")
    league = create_league(client, owner_token, fill_league=True)
    member_token = league["member_token"]
    first_team, second_team, first_player, second_player = create_trade_players(db_session, league["id"])

    propose_response = client.post(
        f"/leagues/{league['id']}/trades",
        json=trade_offer_payload(first_team, second_team, first_player, second_player),
        headers=auth_headers(owner_token),
    )
    assert propose_response.status_code == 201
    trade_id = propose_response.json()["id"]
    assert propose_response.json()["status"] == "proposed"

    accept_response = client.post(f"/trades/{trade_id}/accept", headers=auth_headers(member_token))
    assert accept_response.status_code == 200
    assert accept_response.json()["status"] == "commissioner_review"

    db_session.expire_all()
    assert db_session.query(RosterEntry).filter(RosterEntry.team_id == first_team.id, RosterEntry.player_id == first_player.id).count() == 1
    assert db_session.query(RosterEntry).filter(RosterEntry.team_id == second_team.id, RosterEntry.player_id == second_player.id).count() == 1

    approve_response = client.post(
        f"/trades/{trade_id}/commissioner/approve",
        json={"reason": "Fair trade"},
        headers=auth_headers(owner_token),
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == "processed"

    db_session.expire_all()
    assert db_session.query(RosterEntry).filter(RosterEntry.team_id == first_team.id, RosterEntry.player_id == second_player.id).count() == 1
    assert db_session.query(RosterEntry).filter(RosterEntry.team_id == second_team.id, RosterEntry.player_id == first_player.id).count() == 1
    assert db_session.query(Transaction).filter(Transaction.league_id == league["id"], Transaction.transaction_type == "trade").count() == 2
    assert db_session.query(NotificationLog).filter(NotificationLog.alert_type.in_(["TRADE_PROPOSED", "TRADE_ACCEPTED", "TRADE_PROCESSED"])).count() >= 3
    assert db_session.query(AuditEvent).filter(AuditEvent.action.in_(["trade.proposed", "trade.accepted", "trade.approved"])).count() == 3


def test_trade_accept_rejects_if_roster_changed(client, db_session):
    owner_token = create_user_and_token(client, "stale-owner")
    league = create_league(client, owner_token, fill_league=True)
    member_token = league["member_token"]
    first_team, second_team, first_player, second_player = create_trade_players(db_session, league["id"])

    propose_response = client.post(
        f"/leagues/{league['id']}/trades",
        json=trade_offer_payload(first_team, second_team, first_player, second_player),
        headers=auth_headers(owner_token),
    )
    assert propose_response.status_code == 201
    stale_entry = db_session.query(RosterEntry).filter(RosterEntry.team_id == first_team.id, RosterEntry.player_id == first_player.id).one()
    db_session.delete(stale_entry)
    db_session.commit()

    accept_response = client.post(f"/trades/{propose_response.json()['id']}/accept", headers=auth_headers(member_token))

    assert accept_response.status_code == 409
    assert accept_response.json()["detail"] == "trade player is no longer on offering team"


def test_trade_cancel_reject_and_expiry_paths(client, db_session):
    owner_token = create_user_and_token(client, "paths-owner")
    league = create_league(client, owner_token, fill_league=True)
    member_token = league["member_token"]
    first_team, second_team, first_player, second_player = create_trade_players(db_session, league["id"])

    cancel_response = client.post(
        f"/leagues/{league['id']}/trades",
        json=trade_offer_payload(first_team, second_team, first_player, second_player),
        headers=auth_headers(owner_token),
    )
    assert cancel_response.status_code == 201
    cancelled = client.post(f"/trades/{cancel_response.json()['id']}/cancel", headers=auth_headers(owner_token))
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    reject_response = client.post(
        f"/leagues/{league['id']}/trades",
        json=trade_offer_payload(first_team, second_team, first_player, second_player),
        headers=auth_headers(owner_token),
    )
    assert reject_response.status_code == 201
    rejected = client.post(
        f"/trades/{reject_response.json()['id']}/reject",
        json={"reason": "No thanks"},
        headers=auth_headers(member_token),
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"

    expired_payload = trade_offer_payload(first_team, second_team, first_player, second_player)
    expired_payload["expires_at"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    expired_response = client.post(
        f"/leagues/{league['id']}/trades",
        json=expired_payload,
        headers=auth_headers(owner_token),
    )
    assert expired_response.status_code == 201
    expired_accept = client.post(f"/trades/{expired_response.json()['id']}/accept", headers=auth_headers(member_token))
    assert expired_accept.status_code == 409
    assert expired_accept.json()["detail"] == "trade offer expired"


def test_trade_offer_requires_team_owner_and_league_membership(client, db_session):
    owner_token = create_user_and_token(client, "perm-owner")
    outsider_token = create_user_and_token(client, "perm-outsider")
    league = create_league(client, owner_token, fill_league=True)
    member_token = league["member_token"]
    first_team, second_team, first_player, second_player = create_trade_players(db_session, league["id"])

    outsider_response = client.post(
        f"/leagues/{league['id']}/trades",
        json=trade_offer_payload(first_team, second_team, first_player, second_player),
        headers=auth_headers(outsider_token),
    )
    assert outsider_response.status_code == 403

    wrong_owner_response = client.post(
        f"/leagues/{league['id']}/trades",
        json=trade_offer_payload(first_team, second_team, first_player, second_player),
        headers=auth_headers(member_token),
    )
    assert wrong_owner_response.status_code == 403
    assert wrong_owner_response.json()["detail"] == "team ownership required"
