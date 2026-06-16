import pytest
from sqlalchemy.exc import IntegrityError

from api.app.api.routes import trades as trade_routes
from api.app.models.admin_action import AdminAction
from api.app.models.notification import NotificationLog
from api.app.models.roster import RosterEntry
from api.app.models.team import Team
from api.app.models.transaction import Transaction
from api.app.models.trade_offer import TradeOffer


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_user_and_token(client, suffix: str) -> tuple[int, str]:
    response = client.post(
        "/auth/signup",
        json={
            "first_name": f"Trader{suffix}",
            "email": f"trader-{suffix}@example.com",
            "password": "secret123",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    return payload["user"]["id"], payload["access_token"]


def create_league(
    client,
    token: str,
    *,
    roster_slots_json: dict | None = None,
    trade_review_type: str = "commissioner",
) -> dict:
    payload = {
        "basics": {
            "name": "Trade Logic League",
            "season_year": 2026,
            "max_teams": 12,
            "is_private": False,
            "description": "Trade workflow validation",
            "icon_url": None,
        },
        "settings": {
            "scoring_json": {"ppr": 1},
            "roster_slots_json": roster_slots_json
            or {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "BENCH": 4, "IR": 1},
            "playoff_teams": 4,
            "waiver_type": "faab",
            "trade_review_type": trade_review_type,
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
    response = client.post("/leagues", json=payload, headers=auth_headers(token))
    assert response.status_code == 201
    return response.json()["league"]


def create_players(client) -> tuple[int, int]:
    response = client.post(
        "/players",
        json=[
            {
                "external_id": None,
                "name": "Trade Runner",
                "position": "RB",
                "school": "Texas",
                "image_url": None,
            },
            {
                "external_id": None,
                "name": "Trade Receiver",
                "position": "WR",
                "school": "Oregon",
                "image_url": None,
            },
        ],
    )
    assert response.status_code == 201
    rows = response.json()
    return rows[0]["id"], rows[1]["id"]


def create_position_players(client, rows: list[tuple[str, str]]) -> list[int]:
    response = client.post(
        "/players",
        json=[
            {
                "external_id": None,
                "name": name,
                "position": position,
                "school": f"{name} State",
                "image_url": None,
            }
            for name, position in rows
        ],
    )
    assert response.status_code == 201
    return [row["id"] for row in response.json()]


def trade_setup(
    client,
    db_session,
    suffix: str,
    *,
    roster_slots_json: dict | None = None,
    trade_review_type: str = "commissioner",
    player_rows: list[tuple[str, str]] | None = None,
    create_offer: bool = True,
) -> dict:
    owner_user_id, owner_token = create_user_and_token(client, f"{suffix}-owner")
    member_user_id, member_token = create_user_and_token(client, f"{suffix}-member")
    league = create_league(
        client,
        owner_token,
        roster_slots_json=roster_slots_json,
        trade_review_type=trade_review_type,
    )
    join_response = client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token))
    assert join_response.status_code == 200

    teams = db_session.query(Team).filter(Team.league_id == league["id"]).all()
    owner_team = next(team for team in teams if team.owner_user_id == owner_user_id)
    member_team = next(team for team in teams if team.owner_user_id == member_user_id)
    player_ids = create_position_players(client, player_rows or [("Trade Runner", "RB"), ("Trade Receiver", "WR")])

    add_owner = client.post(
        f"/teams/{owner_team.id}/roster",
        json={"player_id": player_ids[0], "slot": "RB", "status": "active"},
        headers=auth_headers(owner_token),
    )
    assert add_owner.status_code == 201, add_owner.text
    add_member = client.post(
        f"/teams/{member_team.id}/roster",
        json={"player_id": player_ids[1], "slot": "WR", "status": "active"},
        headers=auth_headers(member_token),
    )
    assert add_member.status_code == 201, add_member.text

    proposal_ref = None
    if create_offer:
        proposal_response = client.post(
            "/trades/propose",
            json={
                "league_id": league["id"],
                "from_team_id": owner_team.id,
                "to_team_id": member_team.id,
                "give_ids": [player_ids[0]],
                "receive_ids": [player_ids[1]],
                "note": f"{suffix} trade",
            },
            headers=auth_headers(owner_token),
        )
        assert proposal_response.status_code == 201, proposal_response.text
        proposal_ref = proposal_response.json()["proposal_ref"]
    return {
        "owner_user_id": owner_user_id,
        "member_user_id": member_user_id,
        "owner_token": owner_token,
        "member_token": member_token,
        "league": league,
        "owner_team": owner_team,
        "member_team": member_team,
        "give_player_id": player_ids[0],
        "receive_player_id": player_ids[1],
        "proposal_ref": proposal_ref,
    }


def roster_player_ids(db_session, team_id: int) -> set[int]:
    return {
        row.player_id
        for row in db_session.query(RosterEntry).filter(RosterEntry.team_id == team_id).all()
    }


def test_trade_proposal_creates_sender_and_recipient_alerts(client, db_session):
    owner_user_id, owner_token = create_user_and_token(client, "owner")
    member_user_id, member_token = create_user_and_token(client, "member")
    league = create_league(client, owner_token)

    join_response = client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token))
    assert join_response.status_code == 200

    teams = db_session.query(Team).filter(Team.league_id == league["id"]).all()
    owner_team = next(team for team in teams if team.owner_user_id == owner_user_id)
    member_team = next(team for team in teams if team.owner_user_id == member_user_id)

    give_player_id, receive_player_id = create_players(client)

    add_owner = client.post(
        f"/teams/{owner_team.id}/roster",
        json={"player_id": give_player_id, "slot": "RB", "status": "active"},
        headers=auth_headers(owner_token),
    )
    assert add_owner.status_code == 201
    add_member = client.post(
        f"/teams/{member_team.id}/roster",
        json={"player_id": receive_player_id, "slot": "WR", "status": "active"},
        headers=auth_headers(member_token),
    )
    assert add_member.status_code == 201

    proposal_response = client.post(
        "/trades/propose",
        json={
            "league_id": league["id"],
            "from_team_id": owner_team.id,
            "to_team_id": member_team.id,
            "give_ids": [give_player_id],
            "receive_ids": [receive_player_id],
            "note": "Balanced value offer",
        },
        headers=auth_headers(owner_token),
    )
    assert proposal_response.status_code == 201
    payload = proposal_response.json()
    assert payload["message"] == f"Trade offer sent to {member_team.name}."
    assert payload["proposal_ref"].startswith("TR-")

    recipient_alert = (
        db_session.query(NotificationLog)
        .filter(NotificationLog.user_id == member_user_id, NotificationLog.alert_type == "TRADE_SENT")
        .one()
    )
    sender_alert = (
        db_session.query(NotificationLog)
        .filter(NotificationLog.user_id == owner_user_id, NotificationLog.alert_type == "TRADE")
        .one()
    )
    assert recipient_alert.payload["league_id"] == league["id"]
    assert recipient_alert.payload["player_id"] == receive_player_id
    assert recipient_alert.payload["path"] == f"/trade/{league['id']}"
    assert sender_alert.payload["player_id"] == give_player_id
    assert sender_alert.payload["proposal_ref"] == recipient_alert.payload["proposal_ref"]


def test_trade_proposal_requires_sending_team_ownership(client, db_session):
    owner_user_id, owner_token = create_user_and_token(client, "owner-two")
    member_user_id, member_token = create_user_and_token(client, "member-two")
    league = create_league(client, owner_token)

    join_response = client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token))
    assert join_response.status_code == 200

    teams = db_session.query(Team).filter(Team.league_id == league["id"]).all()
    owner_team = next(team for team in teams if team.owner_user_id == owner_user_id)
    member_team = next(team for team in teams if team.owner_user_id == member_user_id)

    give_player_id, receive_player_id = create_players(client)
    add_owner = client.post(
        f"/teams/{owner_team.id}/roster",
        json={"player_id": give_player_id, "slot": "RB", "status": "active"},
        headers=auth_headers(owner_token),
    )
    assert add_owner.status_code == 201
    add_member = client.post(
        f"/teams/{member_team.id}/roster",
        json={"player_id": receive_player_id, "slot": "WR", "status": "active"},
        headers=auth_headers(member_token),
    )
    assert add_member.status_code == 201

    forbidden_response = client.post(
        "/trades/propose",
        json={
            "league_id": league["id"],
            "from_team_id": owner_team.id,
            "to_team_id": member_team.id,
            "give_ids": [give_player_id],
            "receive_ids": [receive_player_id],
        },
        headers=auth_headers(member_token),
    )
    assert forbidden_response.status_code == 403
    assert forbidden_response.json()["detail"] == "team ownership required for trade proposals"


def test_trade_offer_lifecycle_list_accept_reject_cancel(client, db_session):
    owner_user_id, owner_token = create_user_and_token(client, "life-owner")
    member_user_id, member_token = create_user_and_token(client, "life-member")
    league = create_league(client, owner_token)
    join_response = client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token))
    assert join_response.status_code == 200

    teams = db_session.query(Team).filter(Team.league_id == league["id"]).all()
    owner_team = next(team for team in teams if team.owner_user_id == owner_user_id)
    member_team = next(team for team in teams if team.owner_user_id == member_user_id)

    give_player_id, receive_player_id = create_players(client)
    add_owner = client.post(
        f"/teams/{owner_team.id}/roster",
        json={"player_id": give_player_id, "slot": "RB", "status": "active"},
        headers=auth_headers(owner_token),
    )
    assert add_owner.status_code == 201
    add_member = client.post(
        f"/teams/{member_team.id}/roster",
        json={"player_id": receive_player_id, "slot": "WR", "status": "active"},
        headers=auth_headers(member_token),
    )
    assert add_member.status_code == 201

    proposal_response = client.post(
        "/trades/propose",
        json={
            "league_id": league["id"],
            "from_team_id": owner_team.id,
            "to_team_id": member_team.id,
            "give_ids": [give_player_id],
            "receive_ids": [receive_player_id],
            "note": "Lifecycle offer",
        },
        headers=auth_headers(owner_token),
    )
    assert proposal_response.status_code == 201
    proposal_ref = proposal_response.json()["proposal_ref"]

    list_response = client.get(
        f"/trades/{league['id']}/offers",
        headers=auth_headers(owner_token),
    )
    assert list_response.status_code == 200
    offers = list_response.json()["data"]
    assert any(row["proposal_ref"] == proposal_ref and row["status"] == "proposed" for row in offers)

    accept_response = client.post(
        f"/trades/{proposal_ref}/accept",
        headers=auth_headers(member_token),
    )
    assert accept_response.status_code == 200
    assert accept_response.json()["status"] == "accepted"

    owner_roster_pre_approval = (
        db_session.query(RosterEntry)
        .filter(RosterEntry.team_id == owner_team.id)
        .all()
    )
    member_roster_pre_approval = (
        db_session.query(RosterEntry)
        .filter(RosterEntry.team_id == member_team.id)
        .all()
    )
    assert any(entry.player_id == give_player_id for entry in owner_roster_pre_approval)
    assert any(entry.player_id == receive_player_id for entry in member_roster_pre_approval)

    approve_response = client.post(
        f"/trades/{proposal_ref}/review/approve",
        headers=auth_headers(owner_token),
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == "completed"

    owner_roster = (
        db_session.query(RosterEntry)
        .filter(RosterEntry.team_id == owner_team.id)
        .all()
    )
    member_roster = (
        db_session.query(RosterEntry)
        .filter(RosterEntry.team_id == member_team.id)
        .all()
    )
    assert any(entry.player_id == receive_player_id for entry in owner_roster)
    assert any(entry.player_id == give_player_id for entry in member_roster)
    transactions = db_session.query(Transaction).filter(Transaction.league_id == league["id"]).all()
    assert {row.transaction_type for row in transactions} >= {"trade_in", "trade_out"}
    audit_actions = db_session.query(AdminAction).filter(AdminAction.league_id == league["id"]).all()
    action_types = {row.action_type for row in audit_actions}
    assert "trade.proposed" in action_types
    assert "trade.accepted" in action_types
    assert "trade.review.approved" in action_types


def test_trade_propose_idempotency_key_replays_without_duplicate_offer(client, db_session):
    owner_user_id, owner_token = create_user_and_token(client, "idem-owner")
    member_user_id, member_token = create_user_and_token(client, "idem-member")
    league = create_league(client, owner_token)

    join_response = client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token))
    assert join_response.status_code == 200

    teams = db_session.query(Team).filter(Team.league_id == league["id"]).all()
    owner_team = next(team for team in teams if team.owner_user_id == owner_user_id)
    member_team = next(team for team in teams if team.owner_user_id == member_user_id)

    give_player_id, receive_player_id = create_players(client)
    add_owner = client.post(
        f"/teams/{owner_team.id}/roster",
        json={"player_id": give_player_id, "slot": "RB", "status": "active"},
        headers=auth_headers(owner_token),
    )
    assert add_owner.status_code == 201
    add_member = client.post(
        f"/teams/{member_team.id}/roster",
        json={"player_id": receive_player_id, "slot": "WR", "status": "active"},
        headers=auth_headers(member_token),
    )
    assert add_member.status_code == 201

    headers = auth_headers(owner_token) | {"Idempotency-Key": "trade-propose-idem-1"}
    payload = {
        "league_id": league["id"],
        "from_team_id": owner_team.id,
        "to_team_id": member_team.id,
        "give_ids": [give_player_id],
        "receive_ids": [receive_player_id],
        "note": "Idem trade",
    }
    first = client.post("/trades/propose", json=payload, headers=headers)
    assert first.status_code == 201
    proposal_ref = first.json()["proposal_ref"]

    second = client.post("/trades/propose", json=payload, headers=headers)
    assert second.status_code == 201
    assert second.json()["proposal_ref"] == proposal_ref

    offers = db_session.query(TradeOffer).filter(TradeOffer.league_id == league["id"]).all()
    assert len(offers) == 1


def test_failed_trade_proposal_rolls_back_offer_and_notifications(client, db_session, monkeypatch):
    owner_user_id, owner_token = create_user_and_token(client, "rollback-owner")
    member_user_id, member_token = create_user_and_token(client, "rollback-member")
    league = create_league(client, owner_token)
    join_response = client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token))
    assert join_response.status_code == 200

    teams = db_session.query(Team).filter(Team.league_id == league["id"]).all()
    owner_team = next(team for team in teams if team.owner_user_id == owner_user_id)
    member_team = next(team for team in teams if team.owner_user_id == member_user_id)

    give_player_id, receive_player_id = create_players(client)
    assert client.post(
        f"/teams/{owner_team.id}/roster",
        json={"player_id": give_player_id, "slot": "RB", "status": "active"},
        headers=auth_headers(owner_token),
    ).status_code == 201
    assert client.post(
        f"/teams/{member_team.id}/roster",
        json={"player_id": receive_player_id, "slot": "WR", "status": "active"},
        headers=auth_headers(member_token),
    ).status_code == 201

    def fail_append_admin_action(*_args, **_kwargs):
        raise RuntimeError("forced trade proposal failure")

    monkeypatch.setattr(trade_routes, "append_admin_action", fail_append_admin_action)

    with pytest.raises(RuntimeError):
        client.post(
            "/trades/propose",
            json={
                "league_id": league["id"],
                "from_team_id": owner_team.id,
                "to_team_id": member_team.id,
                "give_ids": [give_player_id],
                "receive_ids": [receive_player_id],
                "note": "Rollback trade",
            },
            headers=auth_headers(owner_token) | {"Idempotency-Key": "trade-propose-fail"},
        )

    db_session.expire_all()
    offers = db_session.query(TradeOffer).filter(TradeOffer.league_id == league["id"]).all()
    trade_notifications = db_session.query(NotificationLog).filter(NotificationLog.alert_type.like("TRADE%")).all()
    assert offers == []
    assert trade_notifications == []


def test_trade_commissioner_can_veto_pending_review_offer(client, db_session):
    owner_user_id, owner_token = create_user_and_token(client, "veto-owner")
    member_user_id, member_token = create_user_and_token(client, "veto-member")
    league = create_league(client, owner_token)
    join_response = client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token))
    assert join_response.status_code == 200

    teams = db_session.query(Team).filter(Team.league_id == league["id"]).all()
    owner_team = next(team for team in teams if team.owner_user_id == owner_user_id)
    member_team = next(team for team in teams if team.owner_user_id == member_user_id)

    give_player_id, receive_player_id = create_players(client)
    add_owner = client.post(
        f"/teams/{owner_team.id}/roster",
        json={"player_id": give_player_id, "slot": "RB", "status": "active"},
        headers=auth_headers(owner_token),
    )
    assert add_owner.status_code == 201
    add_member = client.post(
        f"/teams/{member_team.id}/roster",
        json={"player_id": receive_player_id, "slot": "WR", "status": "active"},
        headers=auth_headers(member_token),
    )
    assert add_member.status_code == 201

    proposal_response = client.post(
        "/trades/propose",
        json={
            "league_id": league["id"],
            "from_team_id": owner_team.id,
            "to_team_id": member_team.id,
            "give_ids": [give_player_id],
            "receive_ids": [receive_player_id],
            "note": "Commissioner veto scenario",
        },
        headers=auth_headers(owner_token),
    )
    assert proposal_response.status_code == 201
    proposal_ref = proposal_response.json()["proposal_ref"]

    accept_response = client.post(
        f"/trades/{proposal_ref}/accept",
        headers=auth_headers(member_token),
    )
    assert accept_response.status_code == 200
    assert accept_response.json()["status"] == "accepted"

    veto_response = client.post(
        f"/trades/{proposal_ref}/review/veto",
        headers=auth_headers(owner_token),
    )
    assert veto_response.status_code == 200
    assert veto_response.json()["status"] == "vetoed"

    owner_roster = (
        db_session.query(RosterEntry)
        .filter(RosterEntry.team_id == owner_team.id)
        .all()
    )
    member_roster = (
        db_session.query(RosterEntry)
        .filter(RosterEntry.team_id == member_team.id)
        .all()
    )
    assert any(entry.player_id == give_player_id for entry in owner_roster)
    assert any(entry.player_id == receive_player_id for entry in member_roster)


def test_trade_proposal_rejects_duplicate_player_payload(client, db_session):
    setup = trade_setup(client, db_session, "dup-payload", create_offer=False)

    response = client.post(
        "/trades/propose",
        json={
            "league_id": setup["league"]["id"],
            "from_team_id": setup["owner_team"].id,
            "to_team_id": setup["member_team"].id,
            "give_ids": [setup["give_player_id"], setup["give_player_id"]],
            "receive_ids": [setup["receive_player_id"]],
        },
        headers=auth_headers(setup["owner_token"]),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "duplicate give player in trade"
    assert db_session.query(TradeOffer).filter(TradeOffer.league_id == setup["league"]["id"]).count() == 0


def test_trade_completion_rejects_sender_roster_changed_without_partial_mutation(client, db_session):
    setup = trade_setup(client, db_session, "sender-changed")
    proposal_ref = setup["proposal_ref"]
    accept = client.post(f"/trades/{proposal_ref}/accept", headers=auth_headers(setup["member_token"]))
    assert accept.status_code == 200

    give_entry = (
        db_session.query(RosterEntry)
        .filter(RosterEntry.team_id == setup["owner_team"].id, RosterEntry.player_id == setup["give_player_id"])
        .one()
    )
    db_session.delete(give_entry)
    db_session.commit()

    approve = client.post(f"/trades/{proposal_ref}/review/approve", headers=auth_headers(setup["owner_token"]))

    assert approve.status_code == 409
    assert approve.json()["detail"] == "trade invalid: sender roster changed"
    db_session.expire_all()
    assert setup["receive_player_id"] in roster_player_ids(db_session, setup["member_team"].id)
    assert setup["receive_player_id"] not in roster_player_ids(db_session, setup["owner_team"].id)
    offer = db_session.query(TradeOffer).filter(TradeOffer.proposal_ref == proposal_ref).one()
    assert offer.status == "accepted"


def test_trade_completion_rejects_receiver_roster_changed_without_partial_mutation(client, db_session):
    setup = trade_setup(client, db_session, "receiver-changed")
    proposal_ref = setup["proposal_ref"]
    accept = client.post(f"/trades/{proposal_ref}/accept", headers=auth_headers(setup["member_token"]))
    assert accept.status_code == 200

    receive_entry = (
        db_session.query(RosterEntry)
        .filter(RosterEntry.team_id == setup["member_team"].id, RosterEntry.player_id == setup["receive_player_id"])
        .one()
    )
    db_session.delete(receive_entry)
    db_session.commit()

    approve = client.post(f"/trades/{proposal_ref}/review/approve", headers=auth_headers(setup["owner_token"]))

    assert approve.status_code == 409
    assert approve.json()["detail"] == "trade invalid: recipient roster changed"
    db_session.expire_all()
    assert setup["give_player_id"] in roster_player_ids(db_session, setup["owner_team"].id)
    assert setup["give_player_id"] not in roster_player_ids(db_session, setup["member_team"].id)
    offer = db_session.query(TradeOffer).filter(TradeOffer.proposal_ref == proposal_ref).one()
    assert offer.status == "accepted"


def test_trade_completion_rejects_cross_league_offer(client, db_session):
    setup = trade_setup(client, db_session, "cross-league")
    _other_owner_id, other_owner_token = create_user_and_token(client, "cross-other-owner")
    other_league = create_league(client, other_owner_token)
    join_other = client.post(f"/leagues/{other_league['id']}/join", headers=auth_headers(setup["member_token"]))
    assert join_other.status_code == 200

    offer = db_session.query(TradeOffer).filter(TradeOffer.proposal_ref == setup["proposal_ref"]).one()
    offer.league_id = other_league["id"]
    offer.status = "accepted"
    db_session.add(offer)
    db_session.commit()

    approve = client.post(
        f"/trades/{setup['proposal_ref']}/review/approve",
        headers=auth_headers(other_owner_token),
    )

    assert approve.status_code == 409
    assert approve.json()["detail"] == "trade teams must belong to the offer league"
    db_session.expire_all()
    assert setup["give_player_id"] in roster_player_ids(db_session, setup["owner_team"].id)
    assert setup["receive_player_id"] in roster_player_ids(db_session, setup["member_team"].id)


def test_trade_completion_rejects_invalid_status_without_mutation(client, db_session):
    setup = trade_setup(client, db_session, "invalid-status")
    offer = db_session.query(TradeOffer).filter(TradeOffer.proposal_ref == setup["proposal_ref"]).one()
    offer.status = "rejected"
    offer.review_status = "rejected"
    db_session.add(offer)
    db_session.commit()

    approve = client.post(
        f"/trades/{setup['proposal_ref']}/review/approve",
        headers=auth_headers(setup["owner_token"]),
    )

    assert approve.status_code == 409
    assert setup["give_player_id"] in roster_player_ids(db_session, setup["owner_team"].id)
    assert setup["receive_player_id"] in roster_player_ids(db_session, setup["member_team"].id)


def test_trade_completion_rejects_illegal_post_trade_roster(client, db_session):
    setup = trade_setup(
        client,
        db_session,
        "illegal-roster",
        roster_slots_json={"QB": 0, "RB": 1, "WR": 1, "TE": 0, "K": 0, "BENCH": 0, "IR": 0},
    )
    extra_wr_id = create_position_players(client, [("Roster Filler", "WR")])[0]
    add_extra = client.post(
        f"/teams/{setup['owner_team'].id}/roster",
        json={"player_id": extra_wr_id, "slot": "WR", "status": "active"},
        headers=auth_headers(setup["owner_token"]),
    )
    assert add_extra.status_code == 201, add_extra.text
    settings_row = db_session.query(trade_routes.LeagueSettings).filter(
        trade_routes.LeagueSettings.league_id == setup["league"]["id"]
    ).one()
    settings_row.roster_slots_json = {"QB": 0, "RB": 1, "WR": 1, "TE": 0, "K": 0, "BENCH": 0, "IR": 0}
    db_session.add(settings_row)
    db_session.commit()
    accept = client.post(f"/trades/{setup['proposal_ref']}/accept", headers=auth_headers(setup["member_token"]))
    assert accept.status_code == 200

    approve = client.post(
        f"/trades/{setup['proposal_ref']}/review/approve",
        headers=auth_headers(setup["owner_token"]),
    )

    assert approve.status_code == 409
    assert "trade would" in approve.json()["detail"]
    db_session.expire_all()
    assert setup["give_player_id"] in roster_player_ids(db_session, setup["owner_team"].id)
    assert setup["receive_player_id"] in roster_player_ids(db_session, setup["member_team"].id)


def test_trade_completion_integrity_error_returns_409_without_partial_mutation(client, db_session, monkeypatch):
    setup = trade_setup(client, db_session, "integrity-conflict")
    accept = client.post(f"/trades/{setup['proposal_ref']}/accept", headers=auth_headers(setup["member_token"]))
    assert accept.status_code == 200

    def raise_integrity_error(*_args, **_kwargs):
        raise IntegrityError("insert transactions", {}, Exception("forced trade conflict"))

    monkeypatch.setattr(trade_routes, "_record_trade_transaction", raise_integrity_error)

    approve = client.post(
        f"/trades/{setup['proposal_ref']}/review/approve",
        headers=auth_headers(setup["owner_token"]),
    )

    assert approve.status_code == 409
    assert approve.json()["detail"] == "trade completion conflict; refresh and retry"
    db_session.expire_all()
    assert setup["give_player_id"] in roster_player_ids(db_session, setup["owner_team"].id)
    assert setup["receive_player_id"] in roster_player_ids(db_session, setup["member_team"].id)
    offer = db_session.query(TradeOffer).filter(TradeOffer.proposal_ref == setup["proposal_ref"]).one()
    assert offer.status == "accepted"


def test_failed_trade_completion_audit_rolls_back_rosters_and_status(client, db_session, monkeypatch):
    setup = trade_setup(client, db_session, "completion-rollback")
    accept = client.post(f"/trades/{setup['proposal_ref']}/accept", headers=auth_headers(setup["member_token"]))
    assert accept.status_code == 200

    def fail_append_admin_action(*_args, **_kwargs):
        raise RuntimeError("forced completion audit failure")

    monkeypatch.setattr(trade_routes, "append_admin_action", fail_append_admin_action)

    with pytest.raises(RuntimeError):
        client.post(
            f"/trades/{setup['proposal_ref']}/review/approve",
            headers=auth_headers(setup["owner_token"]) | {"Idempotency-Key": "trade-completion-fail"},
        )

    db_session.expire_all()
    assert setup["give_player_id"] in roster_player_ids(db_session, setup["owner_team"].id)
    assert setup["receive_player_id"] in roster_player_ids(db_session, setup["member_team"].id)
    offer = db_session.query(TradeOffer).filter(TradeOffer.proposal_ref == setup["proposal_ref"]).one()
    assert offer.status == "accepted"
