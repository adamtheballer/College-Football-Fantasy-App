from datetime import datetime, timezone

from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.draft_pick import DraftPick
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.services.cfb27_player_sync import load_cfb27_ratings, sync_cfb27_players


def test_players_expose_and_sort_by_sheet_board_rank(client, db_session):
    db_session.add_all(
        [
            Player(name="Later Player", position="RB", school="Georgia", sheet_adp=22.0),
            Player(name="Top Player", position="WR", school="Ohio State", sheet_adp=1.0),
            Player(name="Unranked Player", position="QB", school="Florida", sheet_adp=None),
        ]
    )
    db_session.commit()

    response = client.get("/players", params={"sort": "draft_rank", "limit": 10})
    assert response.status_code == 200
    rows = response.json()["data"]

    assert [row["name"] for row in rows[:3]] == ["Top Player", "Later Player", "Unranked Player"]
    assert rows[0]["board_rank"] == 1
    assert rows[0]["sheet_adp"] == 1.0
    assert rows[1]["board_rank"] == 22


def test_cfb27_source_contains_critical_compare_players():
    ratings = {
        (rating.name, rating.school, rating.position): rating
        for rating in load_cfb27_ratings()
    }

    jeremiah = ratings[("Jeremiah Smith", "Ohio State", "WR")]
    ahmad = ratings[("Ahmad Hardy", "Missouri", "RB")]
    assert jeremiah.overall == 99
    assert ahmad.overall == 96


def test_cfb27_sync_creates_missing_compare_players(client, db_session):
    result = sync_cfb27_players(db_session)

    assert result["total"] == 250
    assert result["created"] == 250
    assert result["missing"] == 250
    ahmad = db_session.query(Player).filter_by(name="Ahmad Hardy", school="Missouri", position="RB").one()
    jeremiah = db_session.query(Player).filter_by(name="Jeremiah Smith", school="Ohio State", position="WR").one()
    assert ahmad.sheet_adp == 1.0
    assert jeremiah.sheet_adp == 1.0
    assert ahmad.external_id.startswith("cfb27:")
    assert jeremiah.external_id.startswith("cfb27:")


def test_cfb27_sync_is_idempotent(client, db_session):
    first = sync_cfb27_players(db_session)
    second = sync_cfb27_players(db_session)

    assert first["created"] == 250
    assert second["created"] == 0
    assert second["updated"] == 0
    assert second["already_present"] == 250
    assert db_session.query(Player).filter_by(name="Jeremiah Smith", school="Ohio State", position="WR").count() == 1


def test_cfb27_sync_preserves_duplicates_but_updates_ranked_canonical_row(client, db_session):
    unranked = Player(name="Ahmad Hardy", position="RB", school="Missouri", sheet_adp=None)
    ranked = Player(name="AHMAD HARDY", position="RB", school="MISSOURI", sheet_adp=12.0)
    db_session.add_all([unranked, ranked])
    db_session.commit()

    sync_cfb27_players(db_session)

    rows = db_session.query(Player).filter(Player.name.ilike("ahmad hardy")).order_by(Player.id.asc()).all()
    assert len(rows) == 2
    db_session.refresh(ranked)
    assert ranked.name == "Ahmad Hardy"
    assert ranked.school == "Missouri"
    assert ranked.sheet_adp == 12.0


def test_players_rank_sort_syncs_cfb27_compare_board(client):
    response = client.get("/players", params={"sort": "rank", "limit": 100})

    assert response.status_code == 200
    rows = response.json()["data"]
    names = {row["name"] for row in rows}
    assert "Ahmad Hardy" in names
    assert "Jeremiah Smith" in names


def test_players_search_syncs_cfb27_compare_board(client):
    jeremiah_response = client.get("/players", params={"search": "Jeremiah Smith", "limit": 10})
    ahmad_response = client.get("/players", params={"search": "Ahmad Hardy", "limit": 10})

    assert jeremiah_response.status_code == 200
    assert ahmad_response.status_code == 200
    assert any(row["name"] == "Jeremiah Smith" for row in jeremiah_response.json()["data"])
    assert any(row["name"] == "Ahmad Hardy" for row in ahmad_response.json()["data"])


def test_players_draft_pool_filters_availability_and_position_set_server_side(client, db_session):
    league = League(name="Server Draft Pool League", season_year=2026, max_teams=12)
    team = Team(league=league, name="Team One", owner_name="Manager One")
    rostered_qb = Player(name="Rostered Quarterback", position="QB", school="Texas", sheet_adp=1.0)
    available_qb = Player(name="Available Quarterback", position="QB", school="Georgia", sheet_adp=2.0)
    available_rb = Player(name="Available Running Back", position="RB", school="Alabama", sheet_adp=3.0)
    available_te = Player(name="Available Tight End", position="TE", school="Miami", sheet_adp=4.0)
    db_session.add_all([league, team, rostered_qb, available_qb, available_rb, available_te])
    db_session.flush()
    db_session.add(
        RosterEntry(
            league_id=league.id,
            team_id=team.id,
            player_id=rostered_qb.id,
            slot="QB",
            status="ACTIVE",
        )
    )
    db_session.commit()

    response = client.get(
        "/players",
        params={
            "league_id": league.id,
            "available_only": "true",
            "position": "QB,RB",
            "sort": "draft_rank",
            "limit": 10,
        },
    )

    assert response.status_code == 200
    rows = response.json()["data"]
    assert [row["name"] for row in rows] == ["Available Quarterback", "Available Running Back"]


def test_available_player_pool_excludes_active_draft_picks(client, db_session):
    league = League(name="Active Draft Availability League", season_year=2026, max_teams=12)
    team = Team(league=league, name="Team One", owner_name="Manager One")
    draft = Draft(
        league_id=0,
        draft_datetime_utc=datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc),
        status="live",
    )
    picked_player = Player(name="Already Picked", position="WR", school="Ohio State", sheet_adp=1.0)
    available_player = Player(name="Still Available", position="WR", school="Texas", sheet_adp=2.0)
    db_session.add_all([league, team, picked_player, available_player])
    db_session.flush()
    draft.league_id = league.id
    db_session.add(draft)
    db_session.flush()
    db_session.add(
        DraftPick(
            draft_id=draft.id,
            team_id=team.id,
            player_id=picked_player.id,
            round_number=1,
            round_pick=1,
            overall_pick=1,
        )
    )
    db_session.commit()

    response = client.get(
        "/players",
        params={
            "league_id": league.id,
            "available_only": "true",
            "position": "WR",
            "sort": "draft_rank",
            "limit": 10,
        },
    )

    assert response.status_code == 200
    rows = response.json()["data"]
    assert [row["name"] for row in rows] == ["Still Available"]


def test_players_search_includes_position(client, db_session):
    db_session.add_all(
        [
            Player(name="Pocket Passer", position="QB", school="Texas", sheet_adp=1.0),
            Player(name="Route Runner", position="WR", school="Ohio State", sheet_adp=2.0),
        ]
    )
    db_session.commit()

    response = client.get("/players", params={"search": "QB", "sort": "draft_rank", "limit": 10})

    assert response.status_code == 200
    rows = response.json()["data"]
    assert [row["name"] for row in rows] == ["Pocket Passer"]


def test_players_pagination_constraints_return_422(client):
    bad_limit = client.get("/players", params={"limit": 101})
    bad_offset = client.get("/players", params={"offset": -1})

    assert bad_limit.status_code == 422
    assert bad_offset.status_code == 422


def test_players_search_runs_before_draft_pool_pagination(client, db_session):
    db_session.add_all(
        [
            Player(
                name=f"Board Player {index:03d}",
                position="RB",
                school="Georgia",
                sheet_adp=float(index),
            )
            for index in range(1, 181)
        ]
    )
    db_session.add(
        Player(
            name="Hidden Deep Board Quarterback",
            position="QB",
            school="Needle State",
            sheet_adp=999.0,
        )
    )
    db_session.commit()

    response = client.get(
        "/players",
        params={
            "search": "Hidden Deep",
            "sort": "draft_rank",
            "limit": 1,
        },
    )

    assert response.status_code == 200
    rows = response.json()["data"]
    assert [row["name"] for row in rows] == ["Hidden Deep Board Quarterback"]
