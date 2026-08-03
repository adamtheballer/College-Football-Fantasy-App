from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path

import pytest

from collegefootballfantasy_api.app.services import cfb27_player_sync
from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.draft_pick import DraftPick
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.services.cfb27_player_sync import (
    load_cfb27_ratings,
    load_reviewed_cfb27_snapshot,
    sync_cfb27_players,
)


def reviewed_test_snapshot():
    fixture_dir = Path(__file__).resolve().parents[1] / "fixtures" / "cfb27"
    return load_reviewed_cfb27_snapshot(
        snapshot_path=fixture_dir / "approved-ratings.csv",
        manifest_path=fixture_dir / "approved-ratings.manifest.json",
    )


def _load_cfb27_seed_migration():
    migration_path = Path(__file__).resolve().parents[2] / "api" / "alembic" / "versions" / "0031_seed_cfb27_players.py"
    spec = importlib.util.spec_from_file_location("cfb27_seed_migration", migration_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_cfb27_fields_migration():
    migration_path = Path(__file__).resolve().parents[2] / "api" / "alembic" / "versions" / "0032_add_cfb27_player_fields.py"
    spec = importlib.util.spec_from_file_location("cfb27_fields_migration", migration_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def test_player_rank_requests_do_not_run_cfb27_sync(client, db_session):
    assert db_session.query(Player).count() == 0

    response = client.get("/players", params={"sort": "rank", "limit": 10})

    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert db_session.query(Player).count() == 0


def test_player_list_excludes_non_power4_rows_and_draft_pool_requires_sheet_projection(client, db_session):
    approved = Player(
        name="Approved Receiver",
        position="WR",
        school="Ohio State",
        sheet_source_sheet_id="canonical-preseason:2026:Big10",
        sheet_projected_season_points=250.0,
    )
    missing_projection = Player(
        name="No Projection Receiver",
        position="WR",
        school="Ohio State",
        sheet_source_sheet_id="canonical-preseason:2026:Big10",
    )
    generated_non_power4 = Player(
        external_id="cfb27:eastonmesser|fau|WR",
        name="Easton Messer",
        position="WR",
        school="FAU",
        cfb27_rank=31,
    )
    db_session.add_all([approved, missing_projection, generated_non_power4])
    db_session.commit()

    all_players = client.get("/players", params={"sort": "rank", "limit": 10})
    draft_pool = client.get("/players", params={"draft_eligible": "true", "sort": "rank", "limit": 10})

    assert all_players.status_code == 200
    assert [row["name"] for row in all_players.json()["data"]] == [
        "Approved Receiver",
        "No Projection Receiver",
    ]
    assert draft_pool.status_code == 200
    assert [row["name"] for row in draft_pool.json()["data"]] == ["Approved Receiver"]


def test_draft_pool_rejects_legacy_power4_records_even_when_they_have_projections(client, db_session):
    canonical = Player(
        name="Snapshot Quarterback",
        position="QB",
        school="Texas",
        sheet_source_sheet_id="canonical-preseason:2026:Big12",
        sheet_projected_season_points=275.0,
    )
    legacy = Player(
        name="Legacy Quarterback",
        position="QB",
        school="Texas",
        sheet_source_sheet_id="sportsdata:2026:Big12",
        sheet_projected_season_points=999.0,
    )
    no_source = Player(
        name="Untracked Quarterback",
        position="QB",
        school="Texas",
        sheet_projected_season_points=998.0,
    )
    db_session.add_all((canonical, legacy, no_source))
    db_session.commit()

    response = client.get("/players", params={"draft_eligible": "true", "sort": "rank", "limit": 10})

    assert response.status_code == 200
    assert [row["name"] for row in response.json()["data"]] == ["Snapshot Quarterback"]


def test_cfb27_source_contains_critical_compare_players():
    ratings = {
        (rating.name, rating.school, rating.position): rating
        for rating in load_cfb27_ratings()
    }

    jeremiah = ratings[("Jeremiah Smith", "Ohio State", "WR")]
    ahmad = ratings[("Ahmad Hardy", "Missouri", "RB")]
    assert jeremiah.overall == 99
    assert ahmad.overall == 96


def test_cfb27_source_overalls_are_not_board_ranks():
    ratings = load_cfb27_ratings()

    assert min(rating.overall for rating in ratings) >= 70
    assert max(rating.overall for rating in ratings) <= 99
    ian_strong = next(rating for rating in ratings if rating.name == "Ian Strong" and rating.position == "WR")
    assert ian_strong.rank == 33
    assert ian_strong.overall == 90


def test_cfb27_sync_rejects_a_board_rank_as_an_overall_rating(tmp_path, monkeypatch):
    source_path = tmp_path / "ratings.json"
    source_path.write_text(
        json.dumps(
            [
                {
                    "rank": 33,
                    "name": "Example Receiver",
                    "school": "Ohio State",
                    "position": "WR",
                    "overall": 33,
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(cfb27_player_sync, "CFB27_SOURCE_PATH", source_path)
    cfb27_player_sync.load_cfb27_ratings.cache_clear()

    with pytest.raises(ValueError, match="expected 70-99"):
        cfb27_player_sync.load_cfb27_ratings()

    cfb27_player_sync.load_cfb27_ratings.cache_clear()


def test_cfb27_seed_migration_uses_backend_rating_source():
    migration = _load_cfb27_seed_migration()
    rows = {
        (row["name"], row["school"], row["position"]): row
        for row in migration._load_cfb27_rows()
    }

    assert migration.down_revision == "0030_align_timestamp_nullability"
    assert len(rows) == len(load_cfb27_ratings())
    assert rows[("Jeremiah Smith", "Ohio State", "WR")]["overall"] == 99
    assert rows[("Ahmad Hardy", "Missouri", "RB")]["overall"] == 96


def test_cfb27_fields_migration_computes_global_and_position_ranks():
    migration = _load_cfb27_fields_migration()
    rows = {
        (row["name"], row["school"], row["position"]): row
        for row in migration._load_cfb27_rows()
    }

    assert migration.down_revision == "0031_seed_cfb27_players"
    assert rows[("Jeremiah Smith", "Ohio State", "WR")]["rank"] == 1
    assert rows[("Jeremiah Smith", "Ohio State", "WR")]["position_rank"] == 1
    assert rows[("Ahmad Hardy", "Missouri", "RB")]["rank"] != rows[("Kewan Lacy", "Ole Miss", "RB")]["rank"]
    assert rows[("Ahmad Hardy", "Missouri", "RB")]["position_rank"] == 1


def test_cfb27_sync_enriches_existing_approved_players_without_creating_player_rows(client, db_session):
    ahmad = Player(
        name="Beta Example",
        position="RB",
        school="Missouri",
        sheet_source_sheet_id="snapshot:2026:SEC",
        sheet_projected_season_points=300.0,
    )
    jeremiah = Player(
        name="Alpha Example",
        position="QB",
        school="Ohio State",
        sheet_source_sheet_id="snapshot:2026:Big10",
        sheet_projected_season_points=350.0,
    )
    non_power4 = Player(name="Easton Messer", position="WR", school="FAU")
    db_session.add_all([ahmad, jeremiah, non_power4])
    db_session.commit()

    result = sync_cfb27_players(db_session, snapshot=reviewed_test_snapshot())

    db_session.refresh(ahmad)
    db_session.refresh(jeremiah)
    db_session.refresh(non_power4)
    assert result["total"] == 4
    assert result["created"] == 0
    assert result["matched"] == 2
    assert result["skipped_non_power4"] > 0
    assert db_session.query(Player).count() == 3
    assert ahmad.cfb27_overall == 90
    assert jeremiah.cfb27_rank == 1
    assert non_power4.cfb27_rank is None


def test_cfb27_sync_is_idempotent_for_existing_approved_players(client, db_session):
    player = Player(
        name="Alpha Example",
        position="QB",
        school="Ohio State",
        sheet_source_sheet_id="snapshot:2026:Big10",
        sheet_projected_season_points=350.0,
    )
    db_session.add(player)
    db_session.commit()

    first = sync_cfb27_players(db_session, snapshot=reviewed_test_snapshot())
    second = sync_cfb27_players(db_session, snapshot=reviewed_test_snapshot())

    assert first["created"] == 0
    assert first["updated"] == 1
    assert second["created"] == 0
    assert second["updated"] == 0
    assert second["already_present"] == 1
    assert db_session.query(Player).filter_by(name="Alpha Example", school="Ohio State", position="QB").count() == 1


def test_cfb27_sync_preserves_duplicates_but_updates_ranked_canonical_row(client, db_session):
    unranked = Player(name="Beta Example", position="RB", school="Missouri", sheet_adp=None)
    ranked = Player(name="BETA EXAMPLE", position="RB", school="MISSOURI", sheet_adp=12.0)
    db_session.add_all([unranked, ranked])
    db_session.commit()

    sync_cfb27_players(db_session, snapshot=reviewed_test_snapshot())

    rows = db_session.query(Player).filter(Player.name.ilike("beta example")).order_by(Player.id.asc()).all()
    assert len(rows) == 2
    db_session.refresh(ranked)
    assert ranked.name == "BETA EXAMPLE"
    assert ranked.school == "MISSOURI"
    assert ranked.sheet_adp == 12.0
    assert ranked.cfb27_position_rank == 1
    assert ranked.cfb27_overall == 90


def test_cfb27_sync_matches_california_alias_without_creating_a_duplicate(client, db_session):
    canonical = Player(name="Gamma Sample", position="WR", school="California", sheet_adp=42.0)
    db_session.add(canonical)
    db_session.commit()

    result = sync_cfb27_players(db_session, snapshot=reviewed_test_snapshot())

    db_session.refresh(canonical)
    assert result["created"] == 0
    assert db_session.query(Player).filter_by(name="Gamma Sample", position="WR").count() == 1
    assert canonical.school == "California"
    assert canonical.cfb27_rank == 3
    assert canonical.cfb27_overall == 88


def test_players_rank_sort_uses_cfb27_compare_board(client, db_session):
    db_session.add_all(
        [
            Player(name="Alpha Example", position="QB", school="Ohio State"),
            Player(name="Beta Example", position="RB", school="Missouri"),
        ]
    )
    db_session.commit()
    sync_cfb27_players(db_session, snapshot=reviewed_test_snapshot())

    response = client.get("/players", params={"sort": "rank", "limit": 100})

    assert response.status_code == 200
    rows = response.json()["data"]
    names = {row["name"] for row in rows}
    assert rows[0]["name"] == "Alpha Example"
    assert rows[0]["cfb27_rank"] == 1
    assert rows[0]["cfb27_position_rank"] == 1
    assert rows[0]["board_rank"] == 1
    assert rows[0]["sheet_adp"] is None
    assert "Beta Example" in names
    assert "Alpha Example" in names


def test_players_search_returns_seeded_cfb27_compare_board(client, db_session):
    db_session.add_all(
        [
            Player(name="Alpha Example", position="QB", school="Ohio State"),
            Player(name="Beta Example", position="RB", school="Missouri"),
        ]
    )
    db_session.commit()
    sync_cfb27_players(db_session, snapshot=reviewed_test_snapshot())

    jeremiah_response = client.get("/players", params={"search": "Alpha Example", "limit": 10})
    ahmad_response = client.get("/players", params={"search": "Beta Example", "limit": 10})

    assert jeremiah_response.status_code == 200
    assert ahmad_response.status_code == 200
    jeremiah = next(row for row in jeremiah_response.json()["data"] if row["name"] == "Alpha Example")
    assert jeremiah["board_rank"] == 1
    assert any(row["name"] == "Beta Example" for row in ahmad_response.json()["data"])


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
                school="Texas",
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
