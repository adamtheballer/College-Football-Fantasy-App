from collegefootballfantasy_api.app.models.draft_pick import DraftPick
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.roster import RosterEntry


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_user_and_token(client, suffix: str = "one") -> str:
    response = client.post(
        "/auth/signup",
        json={
            "first_name": f"Coach{suffix}",
            "email": f"coach-{suffix}@example.com",
            "password": "secret123",
        },
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def create_league(client, token: str, roster_slots: dict | None = None) -> dict:
    payload = {
        "basics": {
            "name": "Draft Test League",
            "season_year": 2026,
            "max_teams": 12,
            "is_private": True,
            "description": "Draft room league",
            "icon_url": None,
        },
        "settings": {
            "scoring_json": {"ppr": 1},
            "roster_slots_json": roster_slots or {"QB": 1},
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
    response = client.post(
        "/leagues",
        json=payload,
        headers=auth_headers(token),
    )
    assert response.status_code == 201
    return response.json()["league"]


def create_player(client, name: str = "Arch Manning", position: str = "QB") -> int:
    response = client.post(
        "/players",
        json=[
            {
                "external_id": None,
                "name": name,
                "position": position,
                "school": "Texas",
                "image_url": None,
            }
        ],
    )
    assert response.status_code == 201
    return response.json()[0]["id"]


def fill_roster_except_k(db_session, league_id: int, team_id: int):
    players = [
        Player(name="Filled QB", position="QB", school="Texas"),
        Player(name="Filled RB 1", position="RB", school="Texas"),
        Player(name="Filled RB 2", position="RB", school="Texas"),
        Player(name="Filled WR 1", position="WR", school="Texas"),
        Player(name="Filled WR 2", position="WR", school="Texas"),
        Player(name="Filled TE", position="TE", school="Texas"),
        Player(name="Filled FLEX", position="RB", school="Texas"),
        Player(name="Bench QB", position="QB", school="Texas"),
        Player(name="Bench RB", position="RB", school="Texas"),
        Player(name="Bench WR 1", position="WR", school="Texas"),
        Player(name="Bench TE", position="TE", school="Texas"),
        Player(name="Bench WR 2", position="WR", school="Texas"),
    ]
    db_session.add_all(players)
    db_session.flush()
    slots = ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "BENCH", "BENCH", "BENCH", "BENCH", "BENCH"]
    db_session.add_all(
        [
            RosterEntry(
                league_id=league_id,
                team_id=team_id,
                player_id=player.id,
                slot=slot,
                status="active",
            )
            for player, slot in zip(players, slots, strict=True)
        ]
    )
    db_session.commit()


def test_draft_pick_persists_and_creates_roster_entry(client):
    token = create_user_and_token(client, "draft")
    league = create_league(client, token)
    player_id = create_player(client)

    room_response = client.get(
        f"/leagues/{league['id']}/draft-room",
        headers=auth_headers(token),
    )
    assert room_response.status_code == 200
    room = room_response.json()
    assert room["picks"] == []
    assert room["can_make_pick"] is True
    assert room["user_team_id"] is not None

    pick_response = client.post(
        f"/leagues/{league['id']}/draft-picks",
        json={"player_id": player_id},
        headers=auth_headers(token),
    )
    assert pick_response.status_code == 201
    updated_room = pick_response.json()
    assert len(updated_room["picks"]) == 1
    assert updated_room["picks"][0]["player_id"] == player_id
    assert updated_room["picks"][0]["team_id"] == updated_room["user_team_id"]

    roster_response = client.get(
        f"/teams/{updated_room['user_team_id']}/roster",
        headers=auth_headers(token),
    )
    assert roster_response.status_code == 200
    roster = roster_response.json()
    assert roster["total"] == 1
    assert roster["data"][0]["player"]["id"] == player_id


def test_draft_pick_rejects_position_without_open_roster_slot(client, db_session):
    token = create_user_and_token(client, "draft-illegal-slot")
    roster_slots = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "K": 1, "BENCH": 5}
    league = create_league(client, token, roster_slots=roster_slots)
    room_response = client.get(
        f"/leagues/{league['id']}/draft-room",
        headers=auth_headers(token),
    )
    assert room_response.status_code == 200
    team_id = room_response.json()["user_team_id"]
    fill_roster_except_k(db_session, league["id"], team_id)
    rb_id = create_player(client, "Illegal RB", "RB")

    response = client.post(
        f"/leagues/{league['id']}/draft-picks",
        json={"player_id": rb_id},
        headers=auth_headers(token),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "No open roster slot for this position."
    assert db_session.query(DraftPick).filter(DraftPick.player_id == rb_id).count() == 0
    assert db_session.query(RosterEntry).filter(RosterEntry.player_id == rb_id).count() == 0


def test_draft_pick_allows_kicker_when_only_k_slot_is_open(client, db_session):
    token = create_user_and_token(client, "draft-k-slot")
    roster_slots = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "K": 1, "BENCH": 5}
    league = create_league(client, token, roster_slots=roster_slots)
    room_response = client.get(
        f"/leagues/{league['id']}/draft-room",
        headers=auth_headers(token),
    )
    assert room_response.status_code == 200
    team_id = room_response.json()["user_team_id"]
    fill_roster_except_k(db_session, league["id"], team_id)
    kicker_id = create_player(client, "Legal Kicker", "K")

    response = client.post(
        f"/leagues/{league['id']}/draft-picks",
        json={"player_id": kicker_id},
        headers=auth_headers(token),
    )

    assert response.status_code == 201
    entry = db_session.query(RosterEntry).filter(RosterEntry.player_id == kicker_id).one()
    assert entry.slot == "K"


def test_draft_room_requires_membership(client):
    owner_token = create_user_and_token(client, "draft-owner")
    outsider_token = create_user_and_token(client, "draft-outsider")
    league = create_league(client, owner_token)

    response = client.get(
        f"/leagues/{league['id']}/draft-room",
        headers=auth_headers(outsider_token),
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "league membership required"
