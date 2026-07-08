from collegefootballfantasy_api.app.models.notification import NotificationLog


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_user_and_token(client, suffix: str = "one") -> str:
    response = client.post(
        "/auth/signup",
        json={
            "first_name": f"Coach{suffix}",
            "email": f"coach-{suffix}@example.com",
            "password": "StrongPass123!",
        },
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def create_player(client, name: str = "Watch Player") -> int:
    response = client.post(
        "/players",
        json=[
            {
                "external_id": None,
                "name": name,
                "position": "WR",
                "school": "USC",
                "image_url": None,
            }
        ],
    )
    assert response.status_code == 201
    return response.json()[0]["id"]


def create_league(client, token: str, name: str = "Watch League") -> dict:
    payload = {
        "basics": {
            "name": name,
            "season_year": 2026,
            "max_teams": 2,
            "is_private": True,
            "description": "Watchlist league",
            "icon_url": None,
        },
        "settings": {
            "scoring_json": {"ppr": 1},
            "roster_slots_json": {"QB": 1, "RB": 1, "WR": 1, "TE": 1, "K": 1, "BENCH": 2},
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
    }
    response = client.post("/leagues", json=payload, headers=auth_headers(token))
    assert response.status_code == 201
    return response.json()["league"]


def test_watchlists_persist_per_user(client):
    token = create_user_and_token(client, "owner")
    outsider_token = create_user_and_token(client, "outsider")
    player_id = create_player(client)

    create_response = client.post(
        "/watchlists",
        json={"name": "Targets"},
        headers=auth_headers(token),
    )
    assert create_response.status_code == 201
    watchlist = create_response.json()

    add_response = client.post(
        f"/watchlists/{watchlist['id']}/players",
        json={
            "player_id": player_id,
            "notes": "High-upside target",
            "priority": 1,
            "tags": ["Upside", "  upside ", "late"],
            "alert_injury": False,
        },
        headers=auth_headers(token),
    )
    assert add_response.status_code == 200
    added = add_response.json()
    assert added["players"][0]["id"] == player_id
    assert added["items"][0]["player"]["id"] == player_id
    assert added["items"][0]["notes"] == "High-upside target"
    assert added["items"][0]["priority"] == 1
    assert added["items"][0]["tags"] == ["upside", "late"]
    assert added["items"][0]["alert_injury"] is False

    update_response = client.patch(
        f"/watchlists/{watchlist['id']}/players/{player_id}",
        json={
            "notes": "Moved up after injury news",
            "priority": 2,
            "tags": ["injury-watch"],
            "alert_projection": False,
        },
        headers=auth_headers(token),
    )
    assert update_response.status_code == 200
    updated_item = update_response.json()["items"][0]
    assert updated_item["notes"] == "Moved up after injury news"
    assert updated_item["priority"] == 2
    assert updated_item["tags"] == ["injury-watch"]
    assert updated_item["alert_projection"] is False

    owner_list_response = client.get("/watchlists", headers=auth_headers(token))
    assert owner_list_response.status_code == 200
    assert owner_list_response.json()["total"] == 1
    assert owner_list_response.json()["data"][0]["players"][0]["id"] == player_id
    assert owner_list_response.json()["data"][0]["items"][0]["availability"]["league_id"] is None

    outsider_list_response = client.get("/watchlists", headers=auth_headers(outsider_token))
    assert outsider_list_response.status_code == 200
    assert outsider_list_response.json()["total"] == 0

    outsider_add_response = client.post(
        f"/watchlists/{watchlist['id']}/players",
        json={"player_id": player_id},
        headers=auth_headers(outsider_token),
    )
    assert outsider_add_response.status_code == 404


def test_league_watchlist_is_league_scoped_and_exposes_availability(client):
    token = create_user_and_token(client, "league-owner")
    player_id = create_player(client, "League Watch RB")
    league = create_league(client, token)

    create_response = client.post(
        "/watchlists",
        json={"name": "League Targets", "league_id": league["id"]},
        headers=auth_headers(token),
    )
    assert create_response.status_code == 201
    watchlist = create_response.json()
    assert watchlist["league_id"] == league["id"]

    add_response = client.post(
        f"/watchlists/{watchlist['id']}/players",
        json={"player_id": player_id, "priority": 1, "tags": ["starter"]},
        headers=auth_headers(token),
    )
    assert add_response.status_code == 200
    item = add_response.json()["items"][0]
    assert item["player"]["id"] == player_id
    assert item["availability"]["league_id"] == league["id"]
    assert item["availability"]["status"] == "free_agent"

    list_response = client.get(
        "/watchlists",
        params={"league_id": league["id"]},
        headers=auth_headers(token),
    )
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1
    assert list_response.json()["data"][0]["items"][0]["availability"]["status"] == "free_agent"


def test_watchlist_ownership_alerts_fire_on_roster_add_and_drop(client, db_session):
    token = create_user_and_token(client, "alert-owner")
    player_id = create_player(client, "Watch Alert TE")
    league = create_league(client, token, name="Watch Alert League")
    workspace_response = client.get(f"/leagues/{league['id']}/workspace", headers=auth_headers(token))
    assert workspace_response.status_code == 200
    team_id = workspace_response.json()["owned_team"]["id"]

    create_response = client.post(
        "/watchlists",
        json={"name": "Alert Targets", "league_id": league["id"]},
        headers=auth_headers(token),
    )
    assert create_response.status_code == 201
    watchlist = create_response.json()
    add_watch_response = client.post(
        f"/watchlists/{watchlist['id']}/players",
        json={"player_id": player_id, "alert_ownership": True, "alert_available": True},
        headers=auth_headers(token),
    )
    assert add_watch_response.status_code == 200

    roster_response = client.post(
        f"/teams/{team_id}/roster",
        json={"player_id": player_id, "slot": "BENCH", "status": "active"},
        headers=auth_headers(token),
    )
    assert roster_response.status_code == 201
    roster_entry_id = roster_response.json()["id"]

    drop_response = client.delete(
        f"/teams/{team_id}/roster/{roster_entry_id}",
        headers=auth_headers(token),
    )
    assert drop_response.status_code == 204

    notifications = (
        db_session.query(NotificationLog)
        .filter(NotificationLog.league_id == league["id"], NotificationLog.source_entity_type == "roster")
        .all()
    )
    alert_kinds = {notification.payload["alert_kind"] for notification in notifications}
    assert "ownership_change" in alert_kinds
    assert "available_after_waiver" in alert_kinds
