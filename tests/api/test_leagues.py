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
    return response.json()["user"]["api_token"]


def create_league(client, token: str) -> dict:
    payload = {
        "basics": {
            "name": "Test League",
            "season_year": 2026,
            "max_teams": 12,
            "is_private": True,
            "description": "Workspace league",
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
        "/leagues/create",
        json=payload,
        headers={"X-User-Token": token},
    )
    assert response.status_code == 201
    return response.json()["league"]


def test_create_and_list_leagues(client):
    token = create_user_and_token(client)
    created = create_league(client, token)

    response = client.get("/leagues")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["data"][0]["name"] == created["name"]


def test_league_workspace_returns_membership_owned_team_and_actions(client):
    token = create_user_and_token(client, "workspace")
    league = create_league(client, token)

    response = client.get(
        f"/leagues/{league['id']}/workspace",
        headers={"X-User-Token": token},
    )
    assert response.status_code == 200

    body = response.json()
    assert body["league"]["id"] == league["id"]
    assert body["membership"]["role"] == "commissioner"
    assert body["owned_team"]["league_id"] == league["id"]
    assert body["owned_team"]["owner_user_id"] == league["commissioner_user_id"]
    assert body["roster"] == []
    assert len(body["standings_summary"]) == 1
    assert "manage_roster" in body["allowed_actions"]
    assert "update_settings" in body["allowed_actions"]


def test_league_workspace_requires_membership(client):
    owner_token = create_user_and_token(client, "owner")
    outsider_token = create_user_and_token(client, "outsider")
    league = create_league(client, owner_token)

    response = client.get(
        f"/leagues/{league['id']}/workspace",
        headers={"X-User-Token": outsider_token},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "league membership required"
