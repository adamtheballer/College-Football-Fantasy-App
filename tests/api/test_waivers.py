from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.transaction import Transaction
from collegefootballfantasy_api.app.models.waiver_claim import WaiverClaim


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_user_and_token(client, suffix: str) -> tuple[int, str]:
    response = client.post(
        "/auth/signup",
        json={
            "first_name": f"Waiver{suffix}",
            "email": f"waiver-{suffix}@example.com",
            "password": "secret123",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    return payload["user"]["id"], payload["access_token"]


def create_league(client, token: str, waiver_type: str = "faab") -> dict:
    payload = {
        "basics": {
            "name": "Waiver League",
            "season_year": 2026,
            "max_teams": 12,
            "is_private": False,
            "description": "Waiver workflow testing",
            "icon_url": None,
        },
        "settings": {
            "scoring_json": {"ppr": 1},
            "roster_slots_json": {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "BENCH": 4, "IR": 1},
            "playoff_teams": 4,
            "waiver_type": waiver_type,
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


def create_players(client) -> tuple[int, int, int]:
    response = client.post(
        "/players",
        json=[
            {
                "external_id": None,
                "name": "Waiver RB",
                "position": "RB",
                "school": "Texas",
                "image_url": None,
            },
            {
                "external_id": None,
                "name": "Waiver WR",
                "position": "WR",
                "school": "Oregon",
                "image_url": None,
            },
            {
                "external_id": None,
                "name": "Waiver Target",
                "position": "RB",
                "school": "USC",
                "image_url": None,
            },
        ],
    )
    assert response.status_code == 201
    rows = response.json()
    return rows[0]["id"], rows[1]["id"], rows[2]["id"]


def _team_for_user(db_session, league_id: int, user_id: int) -> Team:
    team = (
        db_session.query(Team)
        .filter(Team.league_id == league_id, Team.owner_user_id == user_id)
        .first()
    )
    assert team is not None
    return team


def test_create_list_and_cancel_waiver_claim(client, db_session):
    owner_user_id, owner_token = create_user_and_token(client, "owner-cancel")
    league = create_league(client, owner_token, waiver_type="faab")
    owner_team = _team_for_user(db_session, league["id"], owner_user_id)

    drop_player_id, _unused_player_id, target_player_id = create_players(client)
    add_response = client.post(
        f"/teams/{owner_team.id}/roster",
        json={"player_id": drop_player_id, "slot": "RB", "status": "active"},
        headers=auth_headers(owner_token),
    )
    assert add_response.status_code == 201

    claim_response = client.post(
        f"/leagues/{league['id']}/waivers/claims",
        json={
            "team_id": owner_team.id,
            "add_player_id": target_player_id,
            "drop_player_id": drop_player_id,
            "bid_amount": 17,
            "note": "Need upside",
        },
        headers=auth_headers(owner_token),
    )
    assert claim_response.status_code == 201
    claim = claim_response.json()
    assert claim["status"] == "pending"
    assert claim["bid_amount"] == 17
    assert claim["add_player_id"] == target_player_id

    list_response = client.get(
        f"/leagues/{league['id']}/waivers/claims",
        headers=auth_headers(owner_token),
    )
    assert list_response.status_code == 200
    listed = list_response.json()["data"]
    assert any(row["id"] == claim["id"] for row in listed)

    cancel_response = client.post(
        f"/leagues/{league['id']}/waivers/claims/{claim['id']}/cancel",
        headers=auth_headers(owner_token),
    )
    assert cancel_response.status_code == 200
    cancelled = cancel_response.json()
    assert cancelled["status"] == "cancelled"


def test_process_waiver_claims_awards_high_bid_and_updates_rosters(client, db_session):
    owner_user_id, owner_token = create_user_and_token(client, "owner-process")
    member_user_id, member_token = create_user_and_token(client, "member-process")
    league = create_league(client, owner_token, waiver_type="faab")

    join_response = client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token))
    assert join_response.status_code == 200

    owner_team = _team_for_user(db_session, league["id"], owner_user_id)
    member_team = _team_for_user(db_session, league["id"], member_user_id)

    owner_drop_player_id, member_drop_player_id, target_player_id = create_players(client)

    owner_add = client.post(
        f"/teams/{owner_team.id}/roster",
        json={"player_id": owner_drop_player_id, "slot": "RB", "status": "active"},
        headers=auth_headers(owner_token),
    )
    assert owner_add.status_code == 201
    member_add = client.post(
        f"/teams/{member_team.id}/roster",
        json={"player_id": member_drop_player_id, "slot": "WR", "status": "active"},
        headers=auth_headers(member_token),
    )
    assert member_add.status_code == 201

    owner_claim = client.post(
        f"/leagues/{league['id']}/waivers/claims",
        json={
            "team_id": owner_team.id,
            "add_player_id": target_player_id,
            "drop_player_id": owner_drop_player_id,
            "bid_amount": 9,
        },
        headers=auth_headers(owner_token),
    )
    assert owner_claim.status_code == 201

    member_claim = client.post(
        f"/leagues/{league['id']}/waivers/claims",
        json={
            "team_id": member_team.id,
            "add_player_id": target_player_id,
            "drop_player_id": member_drop_player_id,
            "bid_amount": 27,
        },
        headers=auth_headers(member_token),
    )
    assert member_claim.status_code == 201

    process_response = client.post(
        f"/leagues/{league['id']}/waivers/process",
        json={},
        headers=auth_headers(owner_token),
    )
    assert process_response.status_code == 200
    body = process_response.json()
    assert body["processed_count"] == 2
    assert body["won_count"] == 1
    assert body["lost_count"] == 1

    winner_row = next(row for row in body["data"] if row["status"] == "won")
    loser_row = next(row for row in body["data"] if row["status"] == "lost")
    assert winner_row["team_id"] == member_team.id
    assert loser_row["team_id"] == owner_team.id

    owner_roster = db_session.query(RosterEntry).filter(RosterEntry.team_id == owner_team.id).all()
    member_roster = db_session.query(RosterEntry).filter(RosterEntry.team_id == member_team.id).all()

    assert all(entry.player_id != target_player_id for entry in owner_roster)
    assert any(entry.player_id == target_player_id for entry in member_roster)

    db_session.expire_all()
    member_team_refreshed = db_session.get(Team, member_team.id)
    assert member_team_refreshed is not None
    assert int(member_team_refreshed.faab_balance) == 73

    transaction_rows = (
        db_session.query(Transaction)
        .filter(Transaction.league_id == league["id"], Transaction.transaction_type == "waiver_add")
        .all()
    )
    assert len(transaction_rows) == 1

    claim_rows = db_session.query(WaiverClaim).filter(WaiverClaim.league_id == league["id"]).all()
    statuses = sorted(row.status for row in claim_rows)
    assert statuses == ["lost", "won"]


def test_create_waiver_claim_idempotency_key_replays_without_duplicate(client, db_session):
    owner_user_id, owner_token = create_user_and_token(client, "owner-claim-idem")
    league = create_league(client, owner_token, waiver_type="faab")
    owner_team = _team_for_user(db_session, league["id"], owner_user_id)

    drop_player_id, _unused_player_id, target_player_id = create_players(client)
    add_response = client.post(
        f"/teams/{owner_team.id}/roster",
        json={"player_id": drop_player_id, "slot": "RB", "status": "active"},
        headers=auth_headers(owner_token),
    )
    assert add_response.status_code == 201

    headers = auth_headers(owner_token) | {"Idempotency-Key": "waiver-claim-idem-1"}
    first = client.post(
        f"/leagues/{league['id']}/waivers/claims",
        json={
            "team_id": owner_team.id,
            "add_player_id": target_player_id,
            "drop_player_id": drop_player_id,
            "bid_amount": 7,
        },
        headers=headers,
    )
    assert first.status_code == 201
    first_id = first.json()["id"]

    second = client.post(
        f"/leagues/{league['id']}/waivers/claims",
        json={
            "team_id": owner_team.id,
            "add_player_id": target_player_id,
            "drop_player_id": drop_player_id,
            "bid_amount": 7,
        },
        headers=headers,
    )
    assert second.status_code == 201
    assert second.json()["id"] == first_id

    claims = db_session.query(WaiverClaim).filter(WaiverClaim.league_id == league["id"]).all()
    assert len(claims) == 1
