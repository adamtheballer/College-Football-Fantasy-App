from datetime import datetime, timedelta, timezone

from api.app.api.routes import leagues as league_routes
from api.app.models.draft import Draft
from api.app.models.draft_pick import DraftPick
from api.app.models.player import Player
from api.app.models.roster import RosterEntry
from api.app.models.team import Team


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_user_and_token(client, suffix: str) -> str:
    response = client.post(
        "/auth/signup",
        json={"first_name": f"Pool{suffix}", "email": f"pool-{suffix}@example.com", "password": "secret123"},
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def create_league(client, token: str) -> dict:
    response = client.post(
        "/leagues",
        json={
            "basics": {
                "name": "Pool League",
                "season_year": 2026,
                "max_teams": 12,
                "is_private": False,
                "description": None,
                "icon_url": None,
            },
            "settings": {
                "scoring_json": {"ppr": 1},
                "roster_slots_json": {"QB": 2, "BENCH": 2},
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
                "order_strategy": "fixed",
            },
        },
        headers=auth_headers(token),
    )
    assert response.status_code == 201
    return response.json()["league"]


def add_player(db_session, name: str, position: str = "QB", school: str = "Texas", adp: float = 1.0) -> Player:
    player = Player(
        external_id=None,
        name=name,
        position=position,
        school=school,
        image_url=None,
        sheet_adp=adp,
        sheet_projected_season_points=100 - adp,
    )
    db_session.add(player)
    db_session.commit()
    db_session.refresh(player)
    return player


def test_list_players_returns_imported_players_and_empty_pool(client, db_session):
    empty = client.get("/players")
    assert empty.status_code == 200
    assert empty.json()["data"] == []

    player = add_player(db_session, "Imported QB")
    response = client.get("/players")
    assert response.status_code == 200
    assert response.json()["data"][0]["id"] == player.id


def test_list_players_search_school_position_and_sort(client, db_session):
    add_player(db_session, "Alpha Runner", "RB", "Ohio State", adp=2)
    add_player(db_session, "Beta Passer", "QB", "Texas", adp=1)

    assert client.get("/players", params={"search": "alpha"}).json()["data"][0]["name"] == "Alpha Runner"
    assert client.get("/players", params={"search": "ohio"}).json()["data"][0]["school"] == "Ohio State"
    position_response = client.get("/players", params={"position": "QB"})
    assert [row["position"] for row in position_response.json()["data"]] == ["QB"]
    sort_response = client.get("/players", params={"sort": "draft_rank"})
    assert [row["name"] for row in sort_response.json()["data"]][:2] == ["Beta Passer", "Alpha Runner"]


def test_list_players_excludes_generated_smoke_rows(client, db_session):
    add_player(db_session, "Smoke Player 1780924455-1", "RB", "Smoke School 1", adp=1)
    add_player(db_session, "Smoke Raw Player 1780924535-1", "RB", "Smoke Raw School 1", adp=2)
    real = add_player(db_session, "Ahmad Hardy", "RB", "Missouri", adp=3)

    response = client.get("/players", params={"limit": 100, "sort": "draft_rank"})

    assert response.status_code == 200
    rows = response.json()["data"]
    assert [row["id"] for row in rows] == [real.id]
    assert all(not row["name"].lower().startswith("smoke") for row in rows)


def test_list_players_dedupes_canonical_players_and_prefers_sheet_board_row(client, db_session):
    sportsdata_row = Player(
        external_id="sportsdata-aaron",
        name="Aaron Philo",
        position="QB",
        school="Florida",
        image_url=None,
        sheet_adp=None,
        sheet_projected_season_points=None,
    )
    sheet_row = Player(
        external_id=None,
        name="Aaron Philo",
        position="QB",
        school="FLORIDA",
        image_url=None,
        sheet_adp=151,
        sheet_projected_season_points=274.92,
        sheet_source_sheet_id="test_sheet",
    )
    db_session.add_all([sportsdata_row, sheet_row, add_player(db_session, "Other QB", adp=1)])
    db_session.commit()

    response = client.get("/players", params={"search": "Aaron Philo", "limit": 100, "sort": "draft_rank"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["data"][0]["id"] == sheet_row.id
    assert payload["data"][0]["sheet_adp"] == 151


def test_list_players_available_only_excludes_rostered_and_drafted_players(client, db_session):
    token = create_user_and_token(client, "available")
    league = create_league(client, token)
    drafted = add_player(db_session, "Drafted QB", adp=1)
    rostered = add_player(db_session, "Rostered QB", adp=2)
    available = add_player(db_session, "Available QB", adp=3)
    team = db_session.query(Team).filter(Team.league_id == league["id"], Team.owner_user_id.isnot(None)).one()
    draft = db_session.query(Draft).filter(Draft.league_id == league["id"]).one()
    db_session.add(
        DraftPick(
            draft_id=draft.id,
            team_id=team.id,
            player_id=drafted.id,
            made_by_user_id=None,
            round_number=1,
            round_pick=1,
            overall_pick=1,
        )
    )
    db_session.add(RosterEntry(league_id=league["id"], team_id=team.id, player_id=rostered.id, slot="QB", status="active"))
    db_session.commit()

    response = client.get(
        "/players",
        params={"league_id": league["id"], "available_only": True, "limit": 100},
        headers=auth_headers(token),
    )
    assert response.status_code == 200
    ids = {row["id"] for row in response.json()["data"]}
    assert available.id in ids
    assert drafted.id not in ids
    assert rostered.id not in ids


def test_list_players_available_only_excludes_canonical_drafted_duplicate(client, db_session):
    token = create_user_and_token(client, "canonical-available")
    league = create_league(client, token)
    drafted = add_player(db_session, "Duplicate Drafted QB", school="Florida", adp=200)
    duplicate = Player(
        external_id="sportsdata-duplicate",
        name="Duplicate Drafted QB",
        position="QB",
        school="FLORIDA",
        image_url=None,
        sheet_adp=None,
        sheet_projected_season_points=None,
    )
    available = add_player(db_session, "Actually Available QB", school="Florida", adp=3)
    team = db_session.query(Team).filter(Team.league_id == league["id"], Team.owner_user_id.isnot(None)).one()
    draft = db_session.query(Draft).filter(Draft.league_id == league["id"]).one()
    db_session.add_all(
        [
            duplicate,
            DraftPick(
                draft_id=draft.id,
                team_id=team.id,
                player_id=drafted.id,
                made_by_user_id=None,
                round_number=1,
                round_pick=1,
                overall_pick=1,
            ),
        ]
    )
    db_session.commit()

    response = client.get(
        "/players",
        params={"available_in_league_id": league["id"], "limit": 100},
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    ids = {row["id"] for row in response.json()["data"]}
    assert available.id in ids
    assert drafted.id not in ids
    assert duplicate.id not in ids


def test_draft_pick_creates_roster_entry_and_removes_player_from_available_pool(client, db_session):
    token = create_user_and_token(client, "pick")
    league = create_league(client, token)
    player = add_player(db_session, "Pickable QB", adp=1)
    draft = db_session.query(Draft).filter(Draft.league_id == league["id"]).one()
    draft.status = "live"
    timer = league_routes._get_or_create_draft_timer_state(db_session, draft.id)
    timer.timer_started_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    timer.paused_at = None
    timer.paused_total_seconds = 0
    db_session.add_all([draft, timer])
    db_session.commit()

    pick = client.post(
        f"/leagues/{league['id']}/draft-picks",
        json={"player_id": player.id},
        headers={**auth_headers(token), "Idempotency-Key": "pool-pick-1"},
    )
    assert pick.status_code == 201
    team = db_session.query(Team).filter(Team.league_id == league["id"], Team.owner_user_id.isnot(None)).one()
    assert db_session.query(RosterEntry).filter(RosterEntry.team_id == team.id, RosterEntry.player_id == player.id).count() == 1

    available = client.get(
        "/players",
        params={"available_in_league_id": league["id"], "limit": 100},
        headers=auth_headers(token),
    )
    assert player.id not in {row["id"] for row in available.json()["data"]}
