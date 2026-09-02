import pytest
from datetime import datetime, timedelta, timezone

from collegefootballfantasy_api.app.api.routes.trades import (
    DEFAULT_ROSTER_SLOTS,
    _normalize_roster_slots,
)
from collegefootballfantasy_api.app.api.routes import admin_trades
from conftest import TestingSessionLocal
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.chat import ChatAuditEvent, ChatMessage, ChatThread
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.lineup_week_snapshot import LineupWeekSnapshot
from collegefootballfantasy_api.app.models.scheduled_notification import ScheduledNotification
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_week_score import PlayerWeekScore
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.trade_offer import TradeOffer
from collegefootballfantasy_api.app.models.trade_review import TradeReview
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.schemas.trade import TradeOfferCreate, TradeOfferRead
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.services import trade_service
from collegefootballfantasy_api.app.services.trade_service import expire_trade_offers_once, process_trade_offers_once
from collegefootballfantasy_api.app.services.chat_service import create_trade_finalized_chat_message


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_user_and_token(client, suffix: str = "trade", *, admin: bool = False) -> str:
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
        user.is_admin = admin
        session.commit()
    return response.json()["access_token"]


def create_league(
    client,
    token: str,
    suffix: str = "trade",
    review_type: str = "none",
    *,
    max_teams: int = 2,
) -> dict:
    response = client.post(
        "/leagues",
        json={
            "basics": {
                "name": f"Trade League {suffix}",
                "season_year": 2026,
                "max_teams": max_teams,
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
    assert len(teams) >= 2
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


def test_trade_offer_contract_uses_canonical_lifecycle_fields():
    canonical_fields = {
        "created_by_user_id",
        "accepted_at",
        "process_after",
        "processed_at",
        "expires_at",
        "failure_reason",
        "countered_from_trade_id",
    }
    model_columns = set(TradeOffer.__table__.columns.keys())
    schema_fields = set(TradeOfferRead.model_fields.keys())

    assert canonical_fields.issubset(model_columns)
    assert canonical_fields.issubset(schema_fields)
    assert "client_request_id" in model_columns
    assert "client_request_id" not in schema_fields
    assert "created_by" not in model_columns
    assert "created_by" not in schema_fields


def test_trade_offer_create_uses_give_receive_items_contract():
    payload = TradeOfferCreate.model_validate(
        {
            "proposing_team_id": 1,
            "receiving_team_id": 2,
            "give_items": [{"team_id": 1, "player_id": 10}],
            "receive_items": [{"team_id": 2, "player_id": 20}],
            "message": "Fair offer",
            "client_request_id": "trade-offer-contract-0001",
        }
    )

    assert payload.give_items[0].team_id == 1
    assert payload.receive_items[0].team_id == 2
    assert payload.client_request_id == "trade-offer-contract-0001"
    assert not hasattr(payload, "proposing_items")
    assert not hasattr(payload, "receiving_items")


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


def test_trade_analyze_returns_an_explicit_unavailable_state_without_published_current_values(client, db_session):
    token = create_user_and_token(client, "analyze-scoring")
    league = create_league(client, token, "analyze-scoring", review_type="none")
    settings = db_session.query(LeagueSettings).filter_by(league_id=league["id"]).one()
    settings.scoring_json = {"ppr": 0}
    receive_player = Player(name="Reception Merchant", position="WR", school="Alpha")
    give_player = Player(name="Empty Projection", position="WR", school="Bravo")
    db_session.add_all([receive_player, give_player])
    db_session.flush()
    db_session.add_all(
        [
            WeeklyProjection(
                player_id=receive_player.id,
                season=2026,
                week=1,
                receptions=10,
                fantasy_points=10,
            ),
            WeeklyProjection(
                player_id=give_player.id,
                season=2026,
                week=1,
                fantasy_points=0,
            ),
        ]
    )
    db_session.commit()
    payload = {
        "receive_ids": [receive_player.id],
        "give_ids": [give_player.id],
        "season": 2026,
        "week": 1,
        "league_size": 2,
        "roster_slots": {"WR": 1, "BE": 0, "IR": 0},
    }

    global_response = client.post("/trade/analyze", json=payload, headers=auth_headers(token))
    league_response = client.post(
        "/trade/analyze",
        json={**payload, "league_id": league["id"]},
        headers=auth_headers(token),
    )

    assert global_response.status_code == 200
    assert global_response.json()["receive_value"] is None
    assert set(global_response.json()["unavailable_player_ids"]) == {receive_player.id, give_player.id}
    assert league_response.status_code == 200
    assert league_response.json()["receive_value"] is None
    assert set(league_response.json()["unavailable_player_ids"]) == {receive_player.id, give_player.id}


def test_trade_analyzer_does_not_substitute_cfb27_or_projection_for_current_value(client, db_session):
    token = create_user_and_token(client, "cfb27-trade-value")
    league = create_league(client, token, "cfb27-trade-value", review_type="none")
    higher_rated_player = Player(
        name="Higher Rated Player",
        position="WR",
        school="Alpha",
        cfb27_overall=99,
    )
    stronger_performer = Player(
        name="Stronger Performer",
        position="WR",
        school="Bravo",
        cfb27_overall=70,
    )
    db_session.add_all([higher_rated_player, stronger_performer])
    db_session.flush()
    db_session.add_all(
        [
            WeeklyProjection(
                player_id=higher_rated_player.id,
                season=2026,
                week=1,
                fantasy_points=10,
            ),
            WeeklyProjection(
                player_id=stronger_performer.id,
                season=2026,
                week=1,
                fantasy_points=10,
            ),
        ]
    )
    db_session.commit()
    payload = {
        "receive_ids": [higher_rated_player.id],
        "give_ids": [stronger_performer.id],
        "season": 2026,
        "week": 1,
        "league_id": league["id"],
        "league_size": 2,
        "roster_slots": {"WR": 1, "BE": 0, "IR": 0},
    }

    week_one_response = client.post("/trade/analyze", json=payload, headers=auth_headers(token))

    assert week_one_response.status_code == 200
    assert week_one_response.json()["receive_value"] is None
    assert set(week_one_response.json()["unavailable_player_ids"]) == {higher_rated_player.id, stronger_performer.id}

    db_session.add_all(
        [
            PlayerWeekScore(
                league_id=league["id"],
                player_id=higher_rated_player.id,
                season=2026,
                week=1,
                fantasy_points=3,
                status="final",
            ),
            PlayerWeekScore(
                league_id=league["id"],
                player_id=stronger_performer.id,
                season=2026,
                week=1,
                fantasy_points=30,
                status="final",
            ),
        ]
    )
    db_session.commit()

    later_week_response = client.post(
        "/trade/analyze",
        json={**payload, "week": 9},
        headers=auth_headers(token),
    )

    assert later_week_response.status_code == 200
    assert later_week_response.json()["receive_value"] is None
    assert set(later_week_response.json()["unavailable_player_ids"]) == {higher_rated_player.id, stronger_performer.id}


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


def test_trade_proposal_queues_an_idempotent_recipient_notification(client, db_session):
    proposing_token = create_user_and_token(client, "proposal-a")
    receiving_token = create_user_and_token(client, "proposal-b")
    league = create_league(client, proposing_token, "proposal")
    join_league(client, receiving_token, league["id"])
    seed = seed_trade_rosters(db_session, league["id"])

    response = client.post(
        f"/leagues/{league['id']}/trades",
        json=trade_offer_payload(seed),
        headers=auth_headers(proposing_token),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "proposed"
    assert body["created_by_user_id"] == seed["proposing"].owner_user_id
    assert "created_by" not in body
    assert body["accepted_at"] is None
    assert body["process_after"] is None
    assert body["processed_at"] is None
    assert body["failure_reason"] is None
    event = db_session.query(ScheduledNotification).filter(ScheduledNotification.event_type == "TRADE_RECEIVED").one()
    assert event.user_id == seed["receiving"].owner_user_id
    assert event.payload["trade_id"] == body["id"]
    assert event.payload["destination"] == {"type": "trade", "league_id": league["id"], "resource_id": body["id"]}

    read_response = client.get(
        f"/leagues/{league['id']}/trades/{body['id']}",
        headers=auth_headers(receiving_token),
    )
    assert read_response.status_code == 200
    assert read_response.json()["id"] == body["id"]

    legacy_response = client.post(
        f"/trade/leagues/{league['id']}/trades",
        json=trade_offer_payload(seed),
        headers=auth_headers(proposing_token),
    )
    assert legacy_response.status_code == 404


def test_trade_proposal_creates_one_private_card_in_a_reused_direct_thread(client, db_session):
    proposing_token = create_user_and_token(client, "private-card-a")
    receiving_token = create_user_and_token(client, "private-card-b")
    league = create_league(client, proposing_token, "private-card")
    join_league(client, receiving_token, league["id"])
    seed = seed_trade_rosters(db_session, league["id"])

    direct_response = client.post(
        f"/leagues/{league['id']}/chats/direct",
        json={"recipient_user_id": seed["receiving"].owner_user_id},
        headers=auth_headers(proposing_token),
    )
    assert direct_response.status_code == 201
    direct_thread_id = direct_response.json()["id"]

    response = client.post(
        f"/leagues/{league['id']}/trades",
        json=trade_offer_payload(seed),
        headers=auth_headers(proposing_token),
    )

    assert response.status_code == 201
    trade_id = response.json()["id"]
    direct_threads = (
        db_session.query(ChatThread)
        .filter_by(league_id=league["id"], thread_type="direct")
        .all()
    )
    assert [thread.id for thread in direct_threads] == [direct_thread_id]
    message = db_session.query(ChatMessage).filter_by(event_key=f"trade:{trade_id}:created").one()
    assert message.thread_id == direct_thread_id
    assert message.message_type == "system"
    assert message.metadata_json["card_type"] == "private_trade_offer"
    assert message.metadata_json["trade_status"] == "proposed"
    assert message.metadata_json["league"] == {"id": league["id"], "name": league["name"]}
    assert message.metadata_json["created_at"] is not None
    assert message.metadata_json["expires_at"] is not None
    assert message.metadata_json["proposing_team_sends"][0]["player_id"] == seed["give"].id
    assert message.metadata_json["receiving_team_sends"][0]["player_id"] == seed["receive"].id

    for token in (proposing_token, receiving_token):
        direct_messages = client.get(
            f"/leagues/{league['id']}/chats/{direct_thread_id}/messages",
            headers=auth_headers(token),
        )
        assert direct_messages.status_code == 200
        cards = [
            row
            for row in direct_messages.json()["data"]
            if row["metadata"].get("card_type") == "private_trade_offer"
        ]
        assert len(cards) == 1
        assert cards[0]["metadata"]["event_key"] == f"trade:{trade_id}:created"


def test_trade_proposal_is_idempotent_and_writes_only_one_private_card(client, db_session):
    proposing_token = create_user_and_token(client, "private-idempotent-a")
    receiving_token = create_user_and_token(client, "private-idempotent-b")
    league = create_league(client, proposing_token, "private-idempotent")
    join_league(client, receiving_token, league["id"])
    seed = seed_trade_rosters(db_session, league["id"])
    payload = {
        **trade_offer_payload(seed),
        "message": "  Fair offer  ",
        "client_request_id": "trade-offer-submit-0001",
    }

    first = client.post(f"/leagues/{league['id']}/trades", json=payload, headers=auth_headers(proposing_token))
    second = client.post(f"/leagues/{league['id']}/trades", json=payload, headers=auth_headers(proposing_token))

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]
    assert first.json()["message"] == "Fair offer"
    assert db_session.query(TradeOffer).filter_by(league_id=league["id"]).count() == 1
    assert db_session.query(ChatThread).filter_by(league_id=league["id"], thread_type="direct").count() == 1
    assert db_session.query(ChatMessage).filter_by(event_key=f"trade:{first.json()['id']}:created").count() == 1
    assert db_session.query(ScheduledNotification).filter_by(event_type="TRADE_RECEIVED").count() == 1

    changed_payload = {**payload, "message": "A different offer under the same request id"}
    conflict = client.post(
        f"/leagues/{league['id']}/trades",
        json=changed_payload,
        headers=auth_headers(proposing_token),
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == "client_request_id was already used for a different trade offer"


def test_trade_offer_rejects_cross_league_team_injection_before_private_card_creation(client, db_session):
    proposing_token = create_user_and_token(client, "private-cross-league-a")
    receiving_token = create_user_and_token(client, "private-cross-league-b")
    foreign_token = create_user_and_token(client, "private-cross-league-c")
    league = create_league(client, proposing_token, "private-cross-league")
    join_league(client, receiving_token, league["id"])
    seed = seed_trade_rosters(db_session, league["id"])
    foreign_league = create_league(client, foreign_token, "private-cross-league-foreign")
    foreign_team = db_session.query(Team).filter_by(league_id=foreign_league["id"]).one()

    injected_payload = {
        **trade_offer_payload(seed),
        "receiving_team_id": foreign_team.id,
        "receive_items": [{"team_id": foreign_team.id, "player_id": seed["receive"].id}],
    }
    response = client.post(
        f"/leagues/{league['id']}/trades",
        json=injected_payload,
        headers=auth_headers(proposing_token),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "team not found in league"
    assert db_session.query(TradeOffer).filter_by(league_id=league["id"]).count() == 0
    assert db_session.query(ChatMessage).filter_by(league_id=league["id"]).count() == 0


def test_private_trade_card_is_invisible_to_another_league_member(client, db_session):
    proposing_token = create_user_and_token(client, "private-access-a")
    receiving_token = create_user_and_token(client, "private-access-b")
    unrelated_token = create_user_and_token(client, "private-access-c")
    league = create_league(client, proposing_token, "private-access", max_teams=4)
    join_league(client, receiving_token, league["id"])
    seed = seed_trade_rosters(db_session, league["id"])
    join_league(client, unrelated_token, league["id"])
    created = client.post(
        f"/leagues/{league['id']}/trades",
        json=trade_offer_payload(seed),
        headers=auth_headers(proposing_token),
    )
    assert created.status_code == 201
    private_message = db_session.query(ChatMessage).filter_by(event_key=f"trade:{created.json()['id']}:created").one()

    blocked = client.get(
        f"/leagues/{league['id']}/chats/{private_message.thread_id}/messages",
        headers=auth_headers(unrelated_token),
    )

    assert blocked.status_code == 404
    assert blocked.json()["detail"] == "chat thread not found"


def test_private_trade_card_fails_closed_for_cpu_or_inactive_owner(client, db_session):
    proposing_token = create_user_and_token(client, "private-cpu-a")
    receiving_token = create_user_and_token(client, "private-cpu-b")
    league = create_league(client, proposing_token, "private-cpu")
    join_league(client, receiving_token, league["id"])
    seed = seed_trade_rosters(db_session, league["id"])
    seed["receiving"].owner_user_id = None
    db_session.commit()

    cpu_offer = client.post(
        f"/leagues/{league['id']}/trades",
        json=trade_offer_payload(seed),
        headers=auth_headers(proposing_token),
    )
    assert cpu_offer.status_code == 422
    assert db_session.query(TradeOffer).filter_by(league_id=league["id"]).count() == 0
    assert db_session.query(ChatMessage).filter_by(league_id=league["id"]).count() == 0

    inactive_proposing_token = create_user_and_token(client, "private-inactive-a")
    inactive_receiving_token = create_user_and_token(client, "private-inactive-b")
    inactive_league = create_league(client, inactive_proposing_token, "private-inactive")
    join_league(client, inactive_receiving_token, inactive_league["id"])
    inactive_seed = seed_trade_rosters(db_session, inactive_league["id"])
    receiving_user = db_session.get(User, inactive_seed["receiving"].owner_user_id)
    assert receiving_user is not None
    receiving_user.is_active = False
    db_session.commit()

    inactive_offer = client.post(
        f"/leagues/{inactive_league['id']}/trades",
        json=trade_offer_payload(inactive_seed),
        headers=auth_headers(inactive_proposing_token),
    )
    assert inactive_offer.status_code == 409
    assert db_session.query(TradeOffer).filter_by(league_id=inactive_league["id"]).count() == 0
    assert db_session.query(ChatMessage).filter_by(league_id=inactive_league["id"]).count() == 0


def test_private_trade_card_failure_rolls_back_trade_and_notification(client, db_session, monkeypatch):
    proposing_token = create_user_and_token(client, "private-atomic-a")
    receiving_token = create_user_and_token(client, "private-atomic-b")
    league = create_league(client, proposing_token, "private-atomic")
    join_league(client, receiving_token, league["id"])
    seed = seed_trade_rosters(db_session, league["id"])

    def fail_private_trade_card(*_args, **_kwargs):
        raise RuntimeError("private chat persistence unavailable")

    monkeypatch.setattr(trade_service, "create_trade_private_chat_message", fail_private_trade_card)
    with pytest.raises(RuntimeError, match="private chat persistence unavailable"):
        client.post(
            f"/leagues/{league['id']}/trades",
            json=trade_offer_payload(seed),
            headers=auth_headers(proposing_token),
        )

    db_session.expire_all()
    assert db_session.query(TradeOffer).filter_by(league_id=league["id"]).count() == 0
    assert db_session.query(ChatMessage).filter_by(league_id=league["id"]).count() == 0
    assert (
        db_session.query(ScheduledNotification)
        .filter_by(user_id=seed["receiving"].owner_user_id, event_type="TRADE_RECEIVED")
        .count()
        == 0
    )


def test_accept_trade_opens_league_vote_card_before_any_roster_swap(client, db_session, monkeypatch):
    monkeypatch.setattr(trade_service, "is_cfb_game_week_active", lambda now=None, timezone_name="UTC": False)
    proposing_token = create_user_and_token(client, "accept-a")
    receiving_token = create_user_and_token(client, "accept-b")
    league = create_league(client, proposing_token, "accept", review_type="none")
    join_league(client, receiving_token, league["id"])
    seed = seed_trade_rosters(db_session, league["id"])
    created = client.post(
        f"/leagues/{league['id']}/trades",
        json=trade_offer_payload(seed),
        headers=auth_headers(proposing_token),
    ).json()

    response = client.post(
        f"/leagues/{league['id']}/trades/{created['id']}/accept",
        json={},
        headers=auth_headers(receiving_token),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "accepted_pending"
    assert payload["accepted_at"] is not None
    assert payload["process_after"] is not None
    assert payload["processed_at"] is None
    db_session.expire_all()
    assert db_session.query(RosterEntry).filter_by(team_id=seed["proposing"].id, player_id=seed["give"].id).one()
    assert db_session.query(RosterEntry).filter_by(team_id=seed["receiving"].id, player_id=seed["receive"].id).one()
    private_created = db_session.query(ChatMessage).filter_by(event_key=f"trade:{created['id']}:created").one()
    private_accepted = db_session.query(ChatMessage).filter_by(event_key=f"trade:{created['id']}:accepted").one()
    assert private_created.thread_id == private_accepted.thread_id
    assert private_accepted.metadata_json["card_type"] == "private_trade_offer"
    assert private_accepted.metadata_json["trade_status"] == "accepted"
    assert db_session.query(ChatMessage).filter_by(event_key=f"trade:{created['id']}:accepted").count() == 1
    replay = client.post(
        f"/leagues/{league['id']}/trades/{created['id']}/accept",
        json={},
        headers=auth_headers(receiving_token),
    )
    assert replay.status_code == 409
    assert db_session.query(ChatMessage).filter_by(event_key=f"trade:{created['id']}:accepted").count() == 1
    message = db_session.query(ChatMessage).filter_by(event_key=f"trade:{created['id']}:league-review").one()
    assert message.metadata_json["event_key"] == message.event_key
    assert message.metadata_json["trade_id"] == created["id"]
    assert message.metadata_json["proposing_team"]["id"] == seed["proposing"].id
    assert message.metadata_json["receiving_team"]["id"] == seed["receiving"].id
    assert message.metadata_json["proposing_team_sends"] == [
        {
            "player_id": seed["give"].id,
            "name": seed["give"].name,
            "position": "QB",
            "school": "Alpha",
        }
    ]
    assert message.metadata_json["receiving_team_sends"] == [
        {
            "player_id": seed["receive"].id,
            "name": seed["receive"].name,
            "position": "RB",
            "school": "Bravo",
        }
    ]
    assert message.metadata_json["review_status"] == "awaiting_votes"
    assert message.metadata_json["votes"] == {
        "uphold_count": 0,
        "veto_count": 0,
        "veto_threshold": 1,
        "eligible_voter_count": 2,
    }
    assert db_session.query(ChatMessage).filter(ChatMessage.event_key == message.event_key).count() == 1
    assert (
        db_session.query(ChatAuditEvent)
        .filter(
            ChatAuditEvent.action == "league_trade_review_message_generated",
            ChatAuditEvent.message_id == message.id,
        )
        .count()
        == 1
    )


def test_due_trade_worker_waits_until_sunday_reset(client, db_session):
    proposing_token = create_user_and_token(client, "worker-a")
    receiving_token = create_user_and_token(client, "worker-b")
    league = create_league(client, proposing_token, "worker", review_type="none")
    join_league(client, receiving_token, league["id"])
    seed = seed_trade_rosters(db_session, league["id"])
    created = client.post(
        f"/leagues/{league['id']}/trades",
        json=trade_offer_payload(seed),
        headers=auth_headers(proposing_token),
    ).json()
    offer = db_session.get(TradeOffer, created["id"])
    offer.status = "accepted_pending"
    offer.accepted_at = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)
    offer.process_after = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)
    db_session.commit()

    result = process_trade_offers_once(
        db_session,
        now=datetime(2026, 9, 3, 16, 0, tzinfo=timezone.utc),
    )

    assert result == {"processed": 0, "failed": 0}
    assert db_session.get(TradeOffer, created["id"]).status == "accepted_pending"
    assert db_session.query(RosterEntry).filter_by(team_id=seed["proposing"].id, player_id=seed["give"].id).one()

    result = process_trade_offers_once(
        db_session,
        now=datetime(2026, 9, 6, 4, 1, tzinfo=timezone.utc),
    )

    assert result == {"processed": 1, "failed": 0}
    assert db_session.query(RosterEntry).filter_by(team_id=seed["receiving"].id, player_id=seed["give"].id).one()
    assert db_session.query(RosterEntry).filter_by(team_id=seed["proposing"].id, player_id=seed["receive"].id).one()
    assert db_session.get(TradeOffer, created["id"]).status == "processed"
    assert db_session.query(TradeReview).filter_by(trade_offer_id=created["id"], action="processed").one()


def test_due_trade_processor_is_idempotent_after_processing(client, db_session, monkeypatch):
    monkeypatch.setattr(trade_service, "is_cfb_game_week_active", lambda now=None, timezone_name="UTC": False)
    proposing_token = create_user_and_token(client, "due-idempotent-a")
    receiving_token = create_user_and_token(client, "due-idempotent-b")
    league = create_league(client, proposing_token, "due-idempotent", review_type="none")
    join_league(client, receiving_token, league["id"])
    seed = seed_trade_rosters(db_session, league["id"])
    created = client.post(
        f"/leagues/{league['id']}/trades",
        json=trade_offer_payload(seed),
        headers=auth_headers(proposing_token),
    ).json()
    offer = db_session.get(TradeOffer, created["id"])
    offer.status = "accepted_pending"
    offer.process_after = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()

    assert process_trade_offers_once(db_session) == {"processed": 1, "failed": 0}
    assert process_trade_offers_once(db_session) == {"processed": 0, "failed": 0}
    assert db_session.query(TradeReview).filter_by(trade_offer_id=created["id"], action="processed").count() == 1


def test_admin_process_due_trades_endpoint_processes_accepted_pending_offer(client, db_session, monkeypatch):
    monkeypatch.setattr(trade_service, "is_cfb_game_week_active", lambda now=None, timezone_name="UTC": False)
    admin_token = create_user_and_token(client, "admin-process", admin=True)
    non_admin_token = create_user_and_token(client, "non-admin-process")
    proposing_token = create_user_and_token(client, "admin-route-a")
    receiving_token = create_user_and_token(client, "admin-route-b")
    league = create_league(client, proposing_token, "admin-route", review_type="none")
    join_league(client, receiving_token, league["id"])
    seed = seed_trade_rosters(db_session, league["id"])
    created = client.post(
        f"/leagues/{league['id']}/trades",
        json=trade_offer_payload(seed),
        headers=auth_headers(proposing_token),
    ).json()
    offer = db_session.get(TradeOffer, created["id"])
    offer.status = "accepted_pending"
    offer.accepted_at = datetime.now(timezone.utc) - timedelta(days=1)
    offer.process_after = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()

    forbidden_response = client.post("/admin/trades/process-due", headers=auth_headers(non_admin_token))
    assert forbidden_response.status_code == 403
    assert forbidden_response.json()["detail"] == "admin only"

    process_response = client.post("/admin/trades/process-due", headers=auth_headers(admin_token))
    assert process_response.status_code == 200
    assert process_response.json() == {"processed": 1, "failed": 0}
    db_session.expire_all()
    assert db_session.query(RosterEntry).filter_by(team_id=seed["receiving"].id, player_id=seed["give"].id).one()
    assert db_session.query(RosterEntry).filter_by(team_id=seed["proposing"].id, player_id=seed["receive"].id).one()
    assert db_session.get(TradeOffer, created["id"]).status == "processed"


def test_admin_due_trade_endpoint_rejects_time_travel_outside_the_e2e_runtime(client, monkeypatch):
    monkeypatch.setattr(admin_trades.settings, "e2e_lifecycle_time_travel_enabled", False)
    admin_token = create_user_and_token(client, "admin-time-travel", admin=True)

    response = client.post(
        "/admin/trades/process-due?as_of=2026-09-07T04%3A01%3A00%2B00%3A00",
        headers=auth_headers(admin_token),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "lifecycle time travel is available only in the E2E runtime"


def test_league_vote_veto_cancels_at_half_of_league_managers(client, db_session, monkeypatch):
    monkeypatch.setattr(trade_service, "is_cfb_game_week_active", lambda now=None, timezone_name="UTC": False)
    proposing_token = create_user_and_token(client, "review-a")
    receiving_token = create_user_and_token(client, "review-b")
    third_token = create_user_and_token(client, "review-c")
    fourth_token = create_user_and_token(client, "review-d")
    league = create_league(client, proposing_token, "review", review_type="commissioner", max_teams=4)
    join_league(client, receiving_token, league["id"])
    join_league(client, third_token, league["id"])
    join_league(client, fourth_token, league["id"])
    seed = seed_trade_rosters(db_session, league["id"])
    created = client.post(
        f"/leagues/{league['id']}/trades",
        json=trade_offer_payload(seed),
        headers=auth_headers(proposing_token),
    ).json()

    accepted = client.post(
        f"/leagues/{league['id']}/trades/{created['id']}/accept",
        json={"reason": "Looks fair"},
        headers=auth_headers(receiving_token),
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted_pending"
    assert db_session.query(RosterEntry).filter_by(team_id=seed["proposing"].id, player_id=seed["give"].id).one()

    first_veto = client.post(
        f"/leagues/{league['id']}/trades/{created['id']}/review-vote",
        json={"action": "veto"},
        headers=auth_headers(third_token),
    )
    assert first_veto.status_code == 200
    assert first_veto.json()["status"] == "accepted_pending"
    assert first_veto.json()["votes"] == {
        "uphold_count": 0,
        "veto_count": 1,
        "veto_threshold": 2,
        "eligible_voter_count": 4,
    }

    vetoed = client.post(
        f"/leagues/{league['id']}/trades/{created['id']}/review-vote",
        json={"action": "veto"},
        headers=auth_headers(fourth_token),
    )
    assert vetoed.status_code == 200
    assert vetoed.json()["status"] == "vetoed"
    db_session.expire_all()
    assert db_session.query(RosterEntry).filter_by(team_id=seed["proposing"].id, player_id=seed["give"].id).one()
    review_message = db_session.query(ChatMessage).filter_by(event_key=f"trade:{created['id']}:league-review").one()
    assert review_message.metadata_json["review_status"] == "vetoed"
    assert review_message.metadata_json["votes"]["veto_count"] == 2


def test_delayed_trade_updates_its_finalized_chat_card_after_processing(client, db_session, monkeypatch):
    game_week_active = {"value": True}
    monkeypatch.setattr(
        trade_service,
        "is_cfb_game_week_active",
        lambda *_args, **_kwargs: game_week_active["value"],
    )
    # A game-week trade is deferred only when an included player has started
    # or kicks off within 24 hours. Keep this chat lifecycle test aligned with
    # that rule instead of assuming every Tuesday--Saturday trade is locked.
    monkeypatch.setattr(
        trade_service,
        "game_starts_for_players",
        lambda _db, *, player_ids, **_kwargs: {
            player_id: datetime.now(timezone.utc) + timedelta(hours=2)
            for player_id in player_ids
        },
    )
    proposing_token = create_user_and_token(client, "chat-pending-a")
    receiving_token = create_user_and_token(client, "chat-pending-b")
    league = create_league(client, proposing_token, "chat-pending", review_type="none")
    join_league(client, receiving_token, league["id"])
    seed = seed_trade_rosters(db_session, league["id"])
    created = client.post(
        f"/leagues/{league['id']}/trades",
        json=trade_offer_payload(seed),
        headers=auth_headers(proposing_token),
    ).json()

    accepted = client.post(
        f"/leagues/{league['id']}/trades/{created['id']}/accept",
        json={},
        headers=auth_headers(receiving_token),
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted_pending"
    # Pending acceptance must not create a "finalized" card before roster
    # movement has actually committed.
    assert db_session.query(ChatMessage).filter_by(event_key=f"trade:{created['id']}:finalized").count() == 0

    offer = db_session.get(TradeOffer, created["id"])
    offer.process_after = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()
    game_week_active["value"] = False

    assert process_trade_offers_once(db_session) == {"processed": 1, "failed": 0}
    db_session.expire_all()
    updated_message = db_session.query(ChatMessage).filter_by(event_key=f"trade:{created['id']}:finalized").one()
    assert updated_message.metadata_json["processing_status"] == "processed"
    assert updated_message.metadata_json["processed_at"] is not None
    assert db_session.query(ChatMessage).filter_by(event_key=f"trade:{created['id']}:finalized").count() == 1


def test_chat_finalization_failure_rolls_back_trade_acceptance(client, db_session, monkeypatch):
    monkeypatch.setattr(trade_service, "is_cfb_game_week_active", lambda now=None, timezone_name="UTC": False)
    proposing_token = create_user_and_token(client, "chat-rollback-a")
    receiving_token = create_user_and_token(client, "chat-rollback-b")
    league = create_league(client, proposing_token, "chat-rollback", review_type="none")
    join_league(client, receiving_token, league["id"])
    seed = seed_trade_rosters(db_session, league["id"])
    created = client.post(
        f"/leagues/{league['id']}/trades",
        json=trade_offer_payload(seed),
        headers=auth_headers(proposing_token),
    ).json()

    def fail_trade_review_card(*_args, **_kwargs):
        raise RuntimeError("chat persistence unavailable")

    monkeypatch.setattr(trade_service, "create_trade_review_chat_message", fail_trade_review_card)
    with pytest.raises(RuntimeError, match="chat persistence unavailable"):
        client.post(
            f"/leagues/{league['id']}/trades/{created['id']}/accept",
            json={},
            headers=auth_headers(receiving_token),
        )

    db_session.expire_all()
    offer = db_session.get(TradeOffer, created["id"])
    assert offer.status == "proposed"
    assert offer.accepted_at is None
    assert offer.processed_at is None
    assert db_session.query(RosterEntry).filter_by(team_id=seed["proposing"].id, player_id=seed["give"].id).one()
    assert db_session.query(RosterEntry).filter_by(team_id=seed["receiving"].id, player_id=seed["receive"].id).one()
    assert db_session.query(ChatMessage).filter_by(event_key=f"trade:{created['id']}:league-review").count() == 0


def test_trade_reject_cancel_counter_and_veto_endpoints(client, db_session):
    proposing_token = create_user_and_token(client, "actions-a")
    receiving_token = create_user_and_token(client, "actions-b")
    league = create_league(client, proposing_token, "actions", review_type="commissioner")
    join_league(client, receiving_token, league["id"])

    seed = seed_trade_rosters(db_session, league["id"])
    rejected = client.post(
        f"/leagues/{league['id']}/trades",
        json=trade_offer_payload(seed),
        headers=auth_headers(proposing_token),
    ).json()
    reject_response = client.post(
        f"/leagues/{league['id']}/trades/{rejected['id']}/reject",
        json={"reason": "No"},
        headers=auth_headers(receiving_token),
    )
    assert reject_response.status_code == 200
    assert reject_response.json()["status"] == "rejected"
    rejected_message = db_session.query(ChatMessage).filter_by(event_key=f"trade:{rejected['id']}:rejected").one()
    assert rejected_message.metadata_json["trade_status"] == "rejected"
    assert db_session.query(RosterEntry).filter_by(team_id=seed["proposing"].id, player_id=seed["give"].id).one()
    assert db_session.query(RosterEntry).filter_by(team_id=seed["receiving"].id, player_id=seed["receive"].id).one()

    seed = seed_trade_rosters(db_session, league["id"])
    cancelled = client.post(
        f"/leagues/{league['id']}/trades",
        json=trade_offer_payload(seed),
        headers=auth_headers(proposing_token),
    ).json()
    cancel_response = client.post(
        f"/leagues/{league['id']}/trades/{cancelled['id']}/cancel",
        json={"reason": "Changed mind"},
        headers=auth_headers(proposing_token),
    )
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"
    cancelled_message = db_session.query(ChatMessage).filter_by(event_key=f"trade:{cancelled['id']}:canceled").one()
    assert cancelled_message.metadata_json["trade_status"] == "cancelled"

    seed = seed_trade_rosters(db_session, league["id"])
    countered = client.post(
        f"/leagues/{league['id']}/trades",
        json=trade_offer_payload(seed),
        headers=auth_headers(proposing_token),
    ).json()
    counter_response = client.post(
        f"/leagues/{league['id']}/trades/{countered['id']}/counter",
        json={
            "proposing_team_id": seed["receiving"].id,
            "receiving_team_id": seed["proposing"].id,
            "give_items": [{"team_id": seed["receiving"].id, "player_id": seed["receive"].id}],
            "receive_items": [{"team_id": seed["proposing"].id, "player_id": seed["give"].id}],
            "message": "Send a better one",
        },
        headers=auth_headers(receiving_token),
    )
    assert counter_response.status_code == 200
    replacement = counter_response.json()
    assert replacement["status"] == "proposed"
    assert replacement["countered_from_trade_id"] == countered["id"]
    assert db_session.get(TradeOffer, countered["id"]).status == "countered"
    assert db_session.query(TradeReview).filter_by(trade_offer_id=countered["id"], action="countered").one()
    assert db_session.query(ChatMessage).filter_by(event_key=f"trade:{countered['id']}:countered").one()
    assert db_session.query(ChatMessage).filter_by(event_key=f"trade:{replacement['id']}:created").one()

    seed = seed_trade_rosters(db_session, league["id"])
    vetoed = client.post(
        f"/leagues/{league['id']}/trades",
        json=trade_offer_payload(seed),
        headers=auth_headers(proposing_token),
    ).json()
    client.post(
        f"/leagues/{league['id']}/trades/{vetoed['id']}/accept",
        json={},
        headers=auth_headers(receiving_token),
    )
    veto_response = client.post(
        f"/leagues/{league['id']}/trades/{vetoed['id']}/review-vote",
        json={"action": "veto"},
        headers=auth_headers(proposing_token),
    )
    assert veto_response.status_code == 200
    assert veto_response.json()["status"] == "vetoed"
    review_message = db_session.query(ChatMessage).filter_by(event_key=f"trade:{vetoed['id']}:league-review").one()
    assert review_message.metadata_json["review_status"] == "vetoed"


def test_started_player_trade_is_accepted_pending_until_sunday(client, db_session, monkeypatch):
    proposing_token = create_user_and_token(client, "locked-a")
    receiving_token = create_user_and_token(client, "locked-b")
    league = create_league(client, proposing_token, "locked", review_type="none")
    join_league(client, receiving_token, league["id"])
    seed = seed_trade_rosters(db_session, league["id"])
    from collegefootballfantasy_api.app.models.game import Game

    current = datetime(2026, 9, 2, 16, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(trade_service, "_utcnow", lambda: current)
    db_session.add(
        Game(
            season=2026,
            week=1,
            season_type="regular",
            start_date=current - timedelta(hours=1),
            home_team=seed["give"].school,
            away_team="Opponent",
        )
    )
    db_session.commit()
    created = client.post(
        f"/leagues/{league['id']}/trades",
        json=trade_offer_payload(seed),
        headers=auth_headers(proposing_token),
    )
    assert created.status_code == 201

    response = client.post(
        f"/leagues/{league['id']}/trades/{created.json()['id']}/accept",
        json={},
        headers=auth_headers(receiving_token),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "accepted_pending"
    assert response.json()["process_after"].startswith("2026-09-06T04:00:00")


def test_trade_review_window_is_twenty_four_hours_when_players_are_not_near_kickoff(client, db_session, monkeypatch):
    proposing_token = create_user_and_token(client, "safe-window-a")
    receiving_token = create_user_and_token(client, "safe-window-b")
    league = create_league(client, proposing_token, "safe-window", review_type="none")
    join_league(client, receiving_token, league["id"])
    seed = seed_trade_rosters(db_session, league["id"])
    current = datetime(2026, 9, 2, 16, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(trade_service, "_utcnow", lambda: current)
    db_session.add(
        Game(
            season=2026,
            week=1,
            season_type="regular",
            start_date=current + timedelta(hours=24, minutes=1),
            home_team=seed["give"].school,
            away_team="Opponent",
        )
    )
    db_session.commit()
    created = client.post(
        f"/leagues/{league['id']}/trades",
        json=trade_offer_payload(seed),
        headers=auth_headers(proposing_token),
    )
    assert created.status_code == 201

    response = client.post(
        f"/leagues/{league['id']}/trades/{created.json()['id']}/accept",
        json={},
        headers=auth_headers(receiving_token),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "accepted_pending"
    assert datetime.fromisoformat(response.json()["process_after"]).replace(tzinfo=timezone.utc) == current + timedelta(hours=24)


def test_trade_with_player_kicking_off_within_24_hours_waits_until_sunday(client, db_session, monkeypatch):
    proposing_token = create_user_and_token(client, "near-kickoff-a")
    receiving_token = create_user_and_token(client, "near-kickoff-b")
    league = create_league(client, proposing_token, "near-kickoff", review_type="none")
    join_league(client, receiving_token, league["id"])
    seed = seed_trade_rosters(db_session, league["id"])
    current = datetime(2026, 9, 2, 16, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(trade_service, "_utcnow", lambda: current)
    db_session.add(
        Game(
            season=2026,
            week=1,
            season_type="regular",
            start_date=current + timedelta(hours=23, minutes=59),
            home_team=seed["give"].school,
            away_team="Opponent",
        )
    )
    db_session.commit()
    created = client.post(
        f"/leagues/{league['id']}/trades",
        json=trade_offer_payload(seed),
        headers=auth_headers(proposing_token),
    )
    assert created.status_code == 201

    response = client.post(
        f"/leagues/{league['id']}/trades/{created.json()['id']}/accept",
        json={},
        headers=auth_headers(receiving_token),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "accepted_pending"


def test_expired_trade_cannot_be_accepted(client, db_session):
    proposing_token = create_user_and_token(client, "expired-a")
    receiving_token = create_user_and_token(client, "expired-b")
    league = create_league(client, proposing_token, "expired", review_type="none")
    join_league(client, receiving_token, league["id"])
    seed = seed_trade_rosters(db_session, league["id"])
    created = client.post(
        f"/leagues/{league['id']}/trades",
        json=trade_offer_payload(seed),
        headers=auth_headers(proposing_token),
    ).json()
    offer = db_session.get(TradeOffer, created["id"])
    offer.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()

    response = client.post(
        f"/leagues/{league['id']}/trades/{created['id']}/accept",
        json={},
        headers=auth_headers(receiving_token),
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "trade offer has expired"


def test_lifecycle_worker_marks_expired_trade_as_final(client, db_session):
    proposing_token = create_user_and_token(client, "expire-worker-a")
    receiving_token = create_user_and_token(client, "expire-worker-b")
    league = create_league(client, proposing_token, "expire-worker")
    join_league(client, receiving_token, league["id"])
    seed = seed_trade_rosters(db_session, league["id"])
    created = client.post(
        f"/leagues/{league['id']}/trades",
        json=trade_offer_payload(seed),
        headers=auth_headers(proposing_token),
    ).json()
    offer = db_session.get(TradeOffer, created["id"])
    offer.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()

    assert expire_trade_offers_once(db_session) == {"expired": 1}
    assert db_session.get(TradeOffer, created["id"]).status == "expired"
    assert db_session.query(TradeReview).filter_by(trade_offer_id=created["id"], action="expired").one()
    expired_message = db_session.query(ChatMessage).filter_by(event_key=f"trade:{created['id']}:expired").one()
    assert expired_message.metadata_json["trade_status"] == "expired"


def test_counter_offer_must_reverse_the_original_participants(client, db_session):
    proposing_token = create_user_and_token(client, "counter-reverse-a")
    receiving_token = create_user_and_token(client, "counter-reverse-b")
    league = create_league(client, proposing_token, "counter-reverse")
    join_league(client, receiving_token, league["id"])
    seed = seed_trade_rosters(db_session, league["id"])
    original = client.post(
        f"/leagues/{league['id']}/trades",
        json=trade_offer_payload(seed),
        headers=auth_headers(proposing_token),
    ).json()

    response = client.post(
        f"/leagues/{league['id']}/trades/{original['id']}/counter",
        json=trade_offer_payload(seed),
        headers=auth_headers(receiving_token),
    )

    assert response.status_code == 400
    assert db_session.get(TradeOffer, original["id"]).status == "proposed"


def test_illegal_trade_plan_does_not_mutate_either_roster(client, db_session, monkeypatch):
    monkeypatch.setattr(trade_service, "is_cfb_game_week_active", lambda now=None, timezone_name="UTC": False)
    proposing_token = create_user_and_token(client, "atomic-a")
    receiving_token = create_user_and_token(client, "atomic-b")
    league = create_league(client, proposing_token, "atomic")
    join_league(client, receiving_token, league["id"])
    seed = seed_trade_rosters(db_session, league["id"])
    created = client.post(
        f"/leagues/{league['id']}/trades",
        json=trade_offer_payload(seed),
        headers=auth_headers(proposing_token),
    ).json()
    settings = db_session.query(LeagueSettings).filter_by(league_id=league["id"]).one()
    settings.roster_slots_json = {"QB": 0, "RB": 0, "WR": 0, "TE": 0, "K": 0, "BENCH": 0}
    db_session.commit()

    response = client.post(
        f"/leagues/{league['id']}/trades/{created['id']}/accept",
        json={},
        headers=auth_headers(receiving_token),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "trade would create an illegal roster"
    db_session.expire_all()
    assert db_session.query(RosterEntry).filter_by(team_id=seed["proposing"].id, player_id=seed["give"].id).one()
    assert db_session.query(RosterEntry).filter_by(team_id=seed["receiving"].id, player_id=seed["receive"].id).one()


def test_trade_offer_list_and_invalid_paths(client, db_session):
    proposing_token = create_user_and_token(client, "list-a")
    receiving_token = create_user_and_token(client, "list-b")
    league = create_league(client, proposing_token, "list", review_type="none")
    join_league(client, receiving_token, league["id"])
    seed = seed_trade_rosters(db_session, league["id"])
    created = client.post(
        f"/leagues/{league['id']}/trades",
        json=trade_offer_payload(seed),
        headers=auth_headers(proposing_token),
    ).json()

    list_response = client.get(f"/leagues/{league['id']}/trades", headers=auth_headers(receiving_token))
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1
    assert list_response.json()["data"][0]["id"] == created["id"]

    invalid_response = client.get(f"/trade/leagues/{league['id']}/trades", headers=auth_headers(receiving_token))
    assert invalid_response.status_code == 404


def test_stale_ownership_fails_before_processing(client, db_session, monkeypatch):
    monkeypatch.setattr(trade_service, "is_cfb_game_week_active", lambda now=None, timezone_name="UTC": False)
    proposing_token = create_user_and_token(client, "stale-a")
    receiving_token = create_user_and_token(client, "stale-b")
    league = create_league(client, proposing_token, "stale", review_type="none")
    join_league(client, receiving_token, league["id"])
    seed = seed_trade_rosters(db_session, league["id"])
    created = client.post(
        f"/leagues/{league['id']}/trades",
        json=trade_offer_payload(seed),
        headers=auth_headers(proposing_token),
    ).json()
    offer = db_session.get(TradeOffer, created["id"])
    offer.status = "accepted_pending"
    offer.accepted_at = datetime.now(timezone.utc) - timedelta(minutes=2)
    offer.process_after = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()
    stale_entry = db_session.query(RosterEntry).filter_by(team_id=seed["proposing"].id, player_id=seed["give"].id).one()
    db_session.delete(stale_entry)
    db_session.commit()

    result = process_trade_offers_once(
        db_session,
        now=datetime.now(timezone.utc),
    )

    assert result == {"processed": 0, "failed": 1}
    failed_offer = db_session.get(TradeOffer, created["id"])
    assert failed_offer.status == "failed"
    assert "no longer" in failed_offer.failure_reason


def test_game_week_trade_proposal_is_allowed_and_deferred(client, db_session):
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
        f"/leagues/{league['id']}/trades",
        json=trade_offer_payload(seed),
        headers=auth_headers(proposing_token),
    )

    assert response.status_code == 201
    assert response.json()["status"] == "proposed"
