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


def create_league(client, token: str) -> dict:
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
            "roster_slots_json": {"QB": 1},
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


def create_player(client, name: str = "Arch Manning") -> int:
    response = client.post(
        "/players",
        json=[
            {
                "external_id": None,
                "name": name,
                "position": "QB",
                "school": "Texas",
                "image_url": None,
            }
        ],
    )
    assert response.status_code == 201
    return response.json()[0]["id"]


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
