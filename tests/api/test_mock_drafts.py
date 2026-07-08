from datetime import datetime, timezone

from conftest import TestingSessionLocal

from collegefootballfantasy_api.app.models.mock_draft import MockDraft
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.user import User


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_user_and_token(client, suffix: str = "one") -> str:
    email = f"mock-{suffix}@example.com"
    response = client.post(
        "/auth/signup",
        json={
            "first_name": f"Mock{suffix}",
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


def create_ranked_players(db_session) -> list[Player]:
    players = [
        Player(name="QB One", position="QB", school="Texas", sheet_adp=1, sheet_projected_season_points=300),
        Player(name="RB One", position="RB", school="Texas", sheet_adp=2, sheet_projected_season_points=250),
        Player(name="WR One", position="WR", school="Texas", sheet_adp=3, sheet_projected_season_points=240),
        Player(name="TE One", position="TE", school="Texas", sheet_adp=4, sheet_projected_season_points=180),
        Player(name="QB Two", position="QB", school="Oregon", sheet_adp=5, sheet_projected_season_points=280),
        Player(name="RB Two", position="RB", school="Oregon", sheet_adp=6, sheet_projected_season_points=220),
        Player(name="WR Two", position="WR", school="Oregon", sheet_adp=7, sheet_projected_season_points=210),
        Player(name="TE Two", position="TE", school="Oregon", sheet_adp=8, sheet_projected_season_points=170),
    ]
    db_session.add_all(players)
    db_session.commit()
    return players


def test_backend_mock_draft_api_creates_queue_picks_cpu_and_export(client, db_session):
    token = create_user_and_token(client, "full")
    players = create_ranked_players(db_session)

    create_response = client.post(
        "/mock-drafts",
        json={
            "title": "Practice Room",
            "league_size": 4,
            "rounds": 2,
            "settings_json": {"roster_slots_json": {"QB": 1, "RB": 1}},
        },
        headers=auth_headers(token),
    )
    assert create_response.status_code == 201
    mock_draft = create_response.json()
    assert mock_draft["status"] == "active"
    assert mock_draft["current_pick"] == 1

    queue_response = client.put(
        f"/mock-drafts/{mock_draft['id']}/queue",
        json={"player_ids": [players[2].id, players[3].id]},
        headers=auth_headers(token),
    )
    assert queue_response.status_code == 200
    assert [row["player_id"] for row in queue_response.json()["queue"]] == [players[2].id, players[3].id]

    pick_response = client.post(
        f"/mock-drafts/{mock_draft['id']}/picks",
        json={"player_id": players[0].id},
        headers=auth_headers(token),
    )
    assert pick_response.status_code == 200
    body = pick_response.json()
    assert body["current_pick"] == 8
    assert len(body["picks"]) == 7
    assert body["picks"][0]["player_id"] == players[0].id
    assert len({pick["player_id"] for pick in body["picks"]}) == 7

    export_response = client.get(f"/mock-drafts/{mock_draft['id']}/export", headers=auth_headers(token))
    assert export_response.status_code == 200
    export = export_response.json()
    assert export["mock_draft_id"] == mock_draft["id"]
    assert len(export["teams"]) == 4
    assert sum(len(team["picks"]) for team in export["teams"]) == 7
    assert db_session.query(RosterEntry).count() == 0


def test_mock_auto_pick_uses_user_queue_then_cpu_advances_to_next_user_turn(client, db_session):
    token = create_user_and_token(client, "queue")
    players = create_ranked_players(db_session)
    create_response = client.post(
        "/mock-drafts",
        json={"title": "Queue Room", "league_size": 4, "rounds": 1},
        headers=auth_headers(token),
    )
    assert create_response.status_code == 201
    mock_draft_id = create_response.json()["id"]
    queue_response = client.put(
        f"/mock-drafts/{mock_draft_id}/queue",
        json={"player_ids": [players[4].id]},
        headers=auth_headers(token),
    )
    assert queue_response.status_code == 200

    auto_response = client.post(f"/mock-drafts/{mock_draft_id}/auto-pick", headers=auth_headers(token))
    assert auto_response.status_code == 200
    body = auto_response.json()
    assert body["status"] == "completed"
    assert body["picks"][0]["player_id"] == players[4].id
    assert len(body["picks"]) == 4
    assert len({pick["player_id"] for pick in body["picks"]}) == 4


def test_mock_draft_full_completion_reset_and_resume(client, db_session):
    token = create_user_and_token(client, "reset")
    players = create_ranked_players(db_session)
    create_response = client.post(
        "/mock-drafts",
        json={"title": "Reset Room", "league_size": 2, "rounds": 2},
        headers=auth_headers(token),
    )
    assert create_response.status_code == 201
    mock_draft_id = create_response.json()["id"]

    first_pick = client.post(
        f"/mock-drafts/{mock_draft_id}/picks",
        json={"player_id": players[0].id},
        headers=auth_headers(token),
    )
    assert first_pick.status_code == 200
    assert first_pick.json()["current_pick"] == 4

    second_pick = client.post(
        f"/mock-drafts/{mock_draft_id}/picks",
        json={"player_id": players[2].id},
        headers=auth_headers(token),
    )
    assert second_pick.status_code == 200
    assert second_pick.json()["status"] == "completed"
    assert len(second_pick.json()["picks"]) == 4

    db_session.query(MockDraft).filter(MockDraft.id == mock_draft_id).update({"status": "paused"})
    db_session.commit()
    resume_response = client.post(f"/mock-drafts/{mock_draft_id}/resume", headers=auth_headers(token))
    assert resume_response.status_code == 409
    assert resume_response.json()["detail"] == "completed mock draft cannot be resumed"

    reset_response = client.post(f"/mock-drafts/{mock_draft_id}/reset", headers=auth_headers(token))
    assert reset_response.status_code == 200
    reset_body = reset_response.json()
    assert reset_body["status"] == "active"
    assert reset_body["current_pick"] == 1
    assert reset_body["picks"] == []


def test_mock_draft_can_import_league_settings(client):
    token = create_user_and_token(client, "import")
    league_payload = {
        "basics": {
            "name": "Mock Source League",
            "season_year": 2026,
            "max_teams": 2,
            "is_private": True,
            "description": None,
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
    league_response = client.post("/leagues", json=league_payload, headers=auth_headers(token))
    assert league_response.status_code == 201
    league_id = league_response.json()["league"]["id"]

    mock_response = client.post(
        "/mock-drafts",
        json={"title": "Imported Settings", "league_size": 2, "rounds": 2, "source_league_id": league_id},
        headers=auth_headers(token),
    )
    assert mock_response.status_code == 201
    settings = mock_response.json()["settings_json"]
    assert settings["source_league_id"] == league_id
    assert settings["roster_slots_json"]["QB"] == 1
    assert settings["kicker_enabled"] is True
