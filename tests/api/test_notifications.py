def create_user(client, suffix: str = "one") -> dict:
    response = client.post(
        "/auth/signup",
        json={
            "first_name": f"Coach{suffix}",
            "email": f"coach-{suffix}@example.com",
            "password": "secret123",
        },
    )
    assert response.status_code == 201
    return response.json()["user"]


def create_league(client, token: str, name: str = "Notify League") -> dict:
    payload = {
        "basics": {
            "name": name,
            "season_year": 2026,
            "max_teams": 12,
            "is_private": True,
            "description": "Notifications league",
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
    response = client.post("/leagues", json=payload, headers={"X-User-Token": token})
    assert response.status_code == 201
    return response.json()["league"]


def test_notification_preferences_are_auth_scoped_without_user_key(client):
    user = create_user(client, "prefs")
    token = user["api_token"]

    initial_response = client.get("/notifications/preferences", headers={"X-User-Token": token})
    assert initial_response.status_code == 200
    assert "user_key" not in initial_response.json()

    update_response = client.post(
        "/notifications/preferences",
        json={
            "push_enabled": False,
            "email_enabled": True,
            "draft_alerts": False,
            "injury_alerts": True,
            "touchdown_alerts": True,
            "usage_alerts": False,
            "waiver_alerts": True,
            "projection_alerts": False,
            "lineup_reminders": True,
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "07:00",
        },
        headers={"X-User-Token": token},
    )
    assert update_response.status_code == 200
    body = update_response.json()
    assert "user_key" not in body
    assert body["push_enabled"] is False
    assert body["touchdown_alerts"] is True
    assert body["quiet_hours_start"] == "22:00"


def test_push_tokens_and_league_preferences_resolve_identity_from_auth(client):
    user = create_user(client, "notify")
    token = user["api_token"]
    league = create_league(client, token)

    token_response = client.post(
        "/notifications/tokens",
        json={"device_token": "device-123", "platform": "ios"},
        headers={"X-User-Token": token},
    )
    assert token_response.status_code == 200
    assert token_response.json()["user_id"] == user["id"]

    prefs_response = client.get("/notifications/league-preferences", headers={"X-User-Token": token})
    assert prefs_response.status_code == 200
    assert prefs_response.json()["data"][0]["league_id"] == league["id"]

    update_response = client.post(
        "/notifications/league-preferences",
        json={
            "items": [
                {
                    "league_id": league["id"],
                    "enabled": True,
                    "injury_alerts": False,
                    "big_play_alerts": True,
                    "projection_alerts": False,
                }
            ]
        },
        headers={"X-User-Token": token},
    )
    assert update_response.status_code == 200
    updated = update_response.json()["data"][0]
    assert updated["league_id"] == league["id"]
    assert updated["injury_alerts"] is False
    assert updated["projection_alerts"] is False
