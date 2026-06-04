from datetime import datetime, timedelta, timezone

from api.app.api.routes import leagues as league_routes
from api.app.models.draft import Draft
from api.app.models.draft_pick import DraftPick
from api.app.models.roster import RosterEntry
from api.app.models.team import Team


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_user_and_token(client) -> str:
    response = client.post(
        "/auth/signup",
        json={
            "first_name": "Available",
            "email": "available-filter@example.com",
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
                "name": "Available Filter League",
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


def create_player(client, name: str) -> int:
    response = client.post(
        "/players",
        json=[
            {
                "external_id": None,
                "name": name,
                "position": "QB",
                "school": "Texas",
                "image_url": None,
                "sheet_adp": 1,
                "sheet_projected_season_points": 100,
            }
        ],
    )
    assert response.status_code == 201
    return response.json()[0]["id"]


def test_available_in_league_excludes_rostered_and_drafted_players(client, db_session):
    token = create_user_and_token(client)
    league = create_league(client, token)
    drafted_player_id = create_player(client, "Drafted Filter QB")
    rostered_player_id = create_player(client, "Rostered Filter QB")
    available_player_id = create_player(client, "Available Filter QB")

    team = db_session.query(Team).filter(Team.league_id == league["id"], Team.owner_user_id.isnot(None)).one()
    draft = db_session.query(Draft).filter(Draft.league_id == league["id"]).one()
    db_session.add(
        DraftPick(
            draft_id=draft.id,
            team_id=team.id,
            player_id=drafted_player_id,
            made_by_user_id=None,
            round_number=1,
            round_pick=1,
            overall_pick=1,
        )
    )
    db_session.add(
        RosterEntry(
            league_id=league["id"],
            team_id=team.id,
            player_id=rostered_player_id,
            slot="QB",
            status="active",
        )
    )
    timer_row = league_routes._get_or_create_draft_timer_state(db_session, draft.id)
    timer_row.timer_started_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.add(timer_row)
    db_session.commit()

    response = client.get(
        f"/players?available_in_league_id={league['id']}&limit=100",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    player_ids = {row["id"] for row in response.json()["data"]}
    assert available_player_id in player_ids
    assert drafted_player_id not in player_ids
    assert rostered_player_id not in player_ids
