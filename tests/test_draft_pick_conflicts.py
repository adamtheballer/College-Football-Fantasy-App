from datetime import datetime, timedelta, timezone

from api.app.api.routes import leagues as league_routes
from api.app.models.draft import Draft
from api.app.models.draft_pick import DraftPick
from api.app.models.league_settings import LeagueSettings
from api.app.models.roster import RosterEntry


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_user_and_token(client, suffix: str = "one") -> str:
    response = client.post(
        "/auth/signup",
        json={
            "first_name": f"Coach{suffix}",
            "email": f"draft-conflict-{suffix}@example.com",
            "password": "secret123",
        },
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def create_league(client, token: str) -> dict:
    response = client.post(
        "/leagues",
        json={
            "basics": {
                "name": "Draft Conflict League",
                "season_year": 2026,
                "max_teams": 12,
                "is_private": False,
                "description": None,
                "icon_url": None,
            },
            "settings": {
                "scoring_json": {"ppr": 1},
                "roster_slots_json": {"QB": 2},
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
        },
        headers=auth_headers(token),
    )
    assert response.status_code == 201
    return response.json()["league"]


def create_player(client, name: str = "Conflict QB") -> int:
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


def force_draft_live(db_session, *, league_id: int) -> None:
    draft_row = db_session.query(Draft).filter(Draft.league_id == league_id).first()
    assert draft_row is not None
    draft_row.status = "live"
    db_session.add(draft_row)
    timer_row = league_routes._get_or_create_draft_timer_state(db_session, draft_row.id)
    timer_row.timer_started_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    timer_row.paused_at = None
    timer_row.paused_total_seconds = 0
    db_session.add(timer_row)
    db_session.commit()


def test_drafting_same_player_twice_returns_409_without_duplicates(client, db_session):
    token = create_user_and_token(client, "same-player")
    league = create_league(client, token)
    player_id = create_player(client)
    force_draft_live(db_session, league_id=league["id"])

    first_response = client.post(
        f"/leagues/{league['id']}/draft-picks",
        json={"player_id": player_id},
        headers=auth_headers(token),
    )
    assert first_response.status_code == 201

    force_draft_live(db_session, league_id=league["id"])
    duplicate_response = client.post(
        f"/leagues/{league['id']}/draft-picks",
        json={"player_id": player_id},
        headers=auth_headers(token),
    )

    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["detail"] in {
        "player already drafted",
        "player already on a league roster",
        "draft state changed; refresh and try again",
    }

    draft_row = db_session.query(Draft).filter(Draft.league_id == league["id"]).one()
    assert db_session.query(DraftPick).filter(DraftPick.draft_id == draft_row.id).count() == 1
    assert db_session.query(RosterEntry).filter(RosterEntry.league_id == league["id"], RosterEntry.player_id == player_id).count() == 1

    room_response = client.get(f"/leagues/{league['id']}/draft-room", headers=auth_headers(token))
    assert room_response.status_code == 200
    room = room_response.json()
    assert len(room["picks"]) == 1
    assert room["drafted_player_ids"] == [player_id]


def test_duplicate_roster_insert_integrity_error_returns_409(client, db_session):
    token = create_user_and_token(client, "roster-integrity")
    league = create_league(client, token)
    player_id = create_player(client, "Roster Conflict QB")
    room = client.get(f"/leagues/{league['id']}/draft-room", headers=auth_headers(token)).json()
    team_id = room["user_team_id"]

    first_response = client.post(
        f"/teams/{team_id}/roster",
        json={"player_id": player_id, "slot": "QB", "status": "active"},
        headers=auth_headers(token),
    )
    assert first_response.status_code == 201

    settings_row = db_session.query(LeagueSettings).filter(LeagueSettings.league_id == league["id"]).one()
    settings_row.roster_slots_json = {"QB": 2}
    db_session.add(settings_row)
    db_session.commit()

    duplicate_response = client.post(
        f"/teams/{team_id}/roster",
        json={"player_id": player_id, "slot": "QB", "status": "active"},
        headers=auth_headers(token),
    )

    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["detail"] == "player already on a league roster"
    assert db_session.query(RosterEntry).filter(RosterEntry.league_id == league["id"], RosterEntry.player_id == player_id).count() == 1
