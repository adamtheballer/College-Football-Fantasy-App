import pytest
from datetime import datetime, timedelta, timezone

from collegefootballfantasy_api.app.api.routes.trades import (
    DEFAULT_ROSTER_SLOTS,
    _normalize_roster_slots,
)
from conftest import TestingSessionLocal
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.league_message import LeagueMessage
from collegefootballfantasy_api.app.models.notification import NotificationLog
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.trade_offer import TradeOffer
from collegefootballfantasy_api.app.models.trade_review import TradeReview
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.services.trade_service import process_trade_offers_once


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


def create_league(client, token: str, suffix: str = "trade", review_type: str = "none") -> dict:
    response = client.post(
        "/leagues",
        json={
            "basics": {
                "name": f"Trade League {suffix}",
                "season_year": 2026,
                "max_teams": 2,
                "is_private": True,
                "description": None,
                "icon_url": None,
            },
            "settings": {
                "scoring_json": {"ppr": 1},
                "roster_slots_json": {"QB": 1, "RB": 1, "WR": 1, "TE": 1, "BENCH": 4, "K": 1, "IR": 1},
                "playoff_teams": 2,
                "waiver_type": "faab",
                "trade_review_type": review_type,
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
        },
        headers=auth_headers(token),
    )
    assert response.status_code == 201
    return response.json()["league"]


def join_league(client, token: str, league_id: int) -> dict:
    response = client.post(f"/leagues/{league_id}/join", headers=auth_headers(token))
    assert response.status_code == 200
    return response.json()


def seed_trade_rosters(db_session, league_id: int) -> dict:
    teams = db_session.query(Team).filter(Team.league_id == league_id).order_by(Team.id.asc()).all()
    assert len(teams) == 2
    players = [
        Player(name="Alpha QB", position="QB", school="Alpha"),
        Player(name="Bravo RB", position="RB", school="Bravo"),
    ]
    db_session.add_all(players)
    db_session.flush()
    db_session.add_all(
        [
            RosterEntry(league_id=league_id, team_id=teams[0].id, player_id=players[0].id, slot="QB", status="active"),
            RosterEntry(league_id=league_id, team_id=teams[1].id, player_id=players[1].id, slot="RB", status="active"),
        ]
    )
    db_session.commit()
    return {"proposing": teams[0], "receiving": teams[1], "give": players[0], "receive": players[1]}


def trade_offer_payload(seed: dict) -> dict:
    return {
        "proposing_team_id": seed["proposing"].id,
        "receiving_team_id": seed["receiving"].id,
        "give_items": [{"team_id": seed["proposing"].id, "player_id": seed["give"].id}],
        "receive_items": [{"team_id": seed["receiving"].id, "player_id": seed["receive"].id}],
        "message": "Fair offer",
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


def test_trade_proposal_creates_recipient_alert(client, db_session):
    proposing_token = create_user_and_token(client, "proposal-a")
    receiving_token = create_user_and_token(client, "proposal-b")
    league = create_league(client, proposing_token, "proposal")
    join_league(client, receiving_token, league["id"])
    seed = seed_trade_rosters(db_session, league["id"])

    response = client.post(
        f"/trade/leagues/{league['id']}/trades",
        json=trade_offer_payload(seed),
        headers=auth_headers(proposing_token),
    )

    assert response.status_code == 201
    assert response.json()["status"] == "proposed"
    alert = db_session.query(NotificationLog).filter(NotificationLog.alert_type == "TRADE_PROPOSED").one()
    assert alert.user_id == seed["receiving"].owner_user_id
    assert alert.payload["trade_id"] == response.json()["id"]


def test_accept_trade_sets_pending_without_swapping_and_writes_chat(client, db_session):
    proposing_token = create_user_and_token(client, "accept-a")
    receiving_token = create_user_and_token(client, "accept-b")
    league = create_league(client, proposing_token, "accept", review_type="none")
    join_league(client, receiving_token, league["id"])
    seed = seed_trade_rosters(db_session, league["id"])
    created = client.post(
        f"/trade/leagues/{league['id']}/trades",
        json=trade_offer_payload(seed),
        headers=auth_headers(proposing_token),
    ).json()

    response = client.post(
        f"/trade/leagues/{league['id']}/trades/{created['id']}/accept",
        json={},
        headers=auth_headers(receiving_token),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "accepted_pending"
    assert payload["accepted_at"] is not None
    assert payload["process_after"] is not None
    assert db_session.query(RosterEntry).filter_by(team_id=seed["proposing"].id, player_id=seed["give"].id).one()
    assert db_session.query(RosterEntry).filter_by(team_id=seed["receiving"].id, player_id=seed["receive"].id).one()
    message = db_session.query(LeagueMessage).filter(LeagueMessage.message_type == "trade").one()
    assert "Trade accepted" in message.body


def test_due_trade_worker_processes_one_business_day_later(client, db_session):
    proposing_token = create_user_and_token(client, "worker-a")
    receiving_token = create_user_and_token(client, "worker-b")
    league = create_league(client, proposing_token, "worker", review_type="none")
    join_league(client, receiving_token, league["id"])
    seed = seed_trade_rosters(db_session, league["id"])
    created = client.post(
        f"/trade/leagues/{league['id']}/trades",
        json=trade_offer_payload(seed),
        headers=auth_headers(proposing_token),
    ).json()
    accepted = client.post(
        f"/trade/leagues/{league['id']}/trades/{created['id']}/accept",
        json={},
        headers=auth_headers(receiving_token),
    ).json()

    result = process_trade_offers_once(
        db_session,
        now=datetime.fromisoformat(accepted["process_after"].replace("Z", "+00:00")) + timedelta(minutes=1),
    )

    assert result == {"processed": 1, "failed": 0}
    assert db_session.query(RosterEntry).filter_by(team_id=seed["receiving"].id, player_id=seed["give"].id).one()
    assert db_session.query(RosterEntry).filter_by(team_id=seed["proposing"].id, player_id=seed["receive"].id).one()
    assert db_session.get(TradeOffer, created["id"]).status == "processed"
    assert db_session.query(TradeReview).filter_by(trade_offer_id=created["id"], action="processed").one()


def test_stale_ownership_fails_before_processing(client, db_session):
    proposing_token = create_user_and_token(client, "stale-a")
    receiving_token = create_user_and_token(client, "stale-b")
    league = create_league(client, proposing_token, "stale", review_type="none")
    join_league(client, receiving_token, league["id"])
    seed = seed_trade_rosters(db_session, league["id"])
    created = client.post(
        f"/trade/leagues/{league['id']}/trades",
        json=trade_offer_payload(seed),
        headers=auth_headers(proposing_token),
    ).json()
    accepted = client.post(
        f"/trade/leagues/{league['id']}/trades/{created['id']}/accept",
        json={},
        headers=auth_headers(receiving_token),
    ).json()
    stale_entry = db_session.query(RosterEntry).filter_by(team_id=seed["proposing"].id, player_id=seed["give"].id).one()
    db_session.delete(stale_entry)
    db_session.commit()

    result = process_trade_offers_once(
        db_session,
        now=datetime.fromisoformat(accepted["process_after"].replace("Z", "+00:00")) + timedelta(minutes=1),
    )

    assert result == {"processed": 0, "failed": 1}
    failed_offer = db_session.get(TradeOffer, created["id"])
    assert failed_offer.status == "failed"
    assert "no longer" in failed_offer.failure_reason


def test_gameday_blocks_trade_proposal(client, db_session):
    proposing_token = create_user_and_token(client, "gameday-a")
    receiving_token = create_user_and_token(client, "gameday-b")
    league = create_league(client, proposing_token, "gameday")
    join_league(client, receiving_token, league["id"])
    seed = seed_trade_rosters(db_session, league["id"])
    db_session.add(
        Game(
            season=2026,
            week=1,
            season_type="regular",
            start_date=datetime.now(timezone.utc) + timedelta(hours=2),
            home_team="Alpha",
            away_team="Other",
        )
    )
    db_session.commit()

    response = client.post(
        f"/trade/leagues/{league['id']}/trades",
        json=trade_offer_payload(seed),
        headers=auth_headers(proposing_token),
    )

    assert response.status_code == 409
    assert "gameday" in response.json()["detail"]
