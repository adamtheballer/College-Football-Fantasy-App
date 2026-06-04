from api.app.models.notification import NotificationLog
from api.app.models.roster import RosterEntry
from api.app.models.team import Team
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


def create_league(client, token: str) -> dict:
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
            "roster_slots_json": {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "BENCH": 4, "IR": 1},
            "playoff_teams": 4,
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
    assert any(row["proposal_ref"] == proposal_ref and row["status"] == "open" for row in offers)

    accept_response = client.post(
        f"/trades/{proposal_ref}/accept",
        headers=auth_headers(member_token),
    )
    assert accept_response.status_code == 200
    assert accept_response.json()["status"] == "pending_review"

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
    assert approve_response.json()["status"] == "accepted"

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
    assert accept_response.json()["status"] == "pending_review"

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
