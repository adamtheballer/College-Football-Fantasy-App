from datetime import datetime, timedelta, timezone

from api.app.api.routes import stats as stats_routes
from api.app.integrations.sportsdata import SportsDataClient
from api.app.models.injury import Injury
from api.app.models.player import Player
from api.app.models.player_stat import PlayerStat
from api.app.models.provider_sync_state import ProviderSyncState
from api.app.services.sportsdata_sync import upsert_power4_standings_snapshot


def test_player_stats_endpoint_uses_db_backed_sportsdata_cache(client, db_session, monkeypatch):
    create_response = client.post(
        "/players",
        json=[
            {
                "external_id": "1001",
                "name": "Cache Tester",
                "position": "QB",
                "school": "Alabama",
            }
        ],
    )
    assert create_response.status_code == 201
    player_id = create_response.json()[0]["id"]

    calls = {"count": 0}

    def fake_get_player_stats(self, external_id, season=None, week=None):
        calls["count"] += 1
        return {"PlayerID": int(external_id), "PassingYards": 312, "Season": season, "Week": week}

    monkeypatch.setattr(SportsDataClient, "get_player_stats", fake_get_player_stats)

    first = client.get(f"/players/{player_id}/stats?season=2025&week=1")
    assert first.status_code == 200
    assert first.json()["cached"] is False
    assert first.json()["stats"]["PassingYards"] == 312
    assert calls["count"] == 1

    provider_state = db_session.query(ProviderSyncState).first()
    assert provider_state is not None
    assert provider_state.provider == "sportsdata"
    assert provider_state.feed == "player_game_stats_week"
    assert provider_state.status == "ready"
    assert provider_state.expires_at is not None

    def fail_if_called(self, external_id, season=None, week=None):
        raise AssertionError("SportsData should not be called while cache is fresh")

    monkeypatch.setattr(SportsDataClient, "get_player_stats", fail_if_called)

    second = client.get(f"/players/{player_id}/stats?season=2025&week=1")
    assert second.status_code == 200
    assert second.json()["cached"] is True
    assert second.json()["stats"]["PassingYards"] == 312


def test_player_stats_endpoint_falls_back_to_stale_cache_when_provider_fails(client, db_session, monkeypatch):
    create_response = client.post(
        "/players",
        json=[
            {
                "external_id": "2002",
                "name": "Stale Cache",
                "position": "RB",
                "school": "Texas",
            }
        ],
    )
    assert create_response.status_code == 201
    player_id = create_response.json()[0]["id"]

    monkeypatch.setattr(
        SportsDataClient,
        "get_player_stats",
        lambda self, external_id, season=None, week=None: {
            "PlayerID": int(external_id),
            "RushingYards": 98,
            "Season": season,
            "Week": week,
        },
    )
    seeded = client.get(f"/players/{player_id}/stats?season=2025&week=2")
    assert seeded.status_code == 200
    assert seeded.json()["stats"]["RushingYards"] == 98

    stat_row = db_session.query(PlayerStat).filter(PlayerStat.player_id == player_id).first()
    assert stat_row is not None
    stat_row.updated_at = datetime.now(timezone.utc) - timedelta(days=45)

    provider_state = db_session.query(ProviderSyncState).first()
    if provider_state:
        provider_state.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    db_session.commit()

    monkeypatch.setattr(
        SportsDataClient,
        "get_player_stats",
        lambda self, external_id, season=None, week=None: (_ for _ in ()).throw(
            RuntimeError("provider unavailable")
        ),
    )

    stale_response = client.get(f"/players/{player_id}/stats?season=2025&week=2")
    assert stale_response.status_code == 200
    payload = stale_response.json()
    assert payload["cached"] is True
    assert payload["stats"] is not None
    assert payload["message"] is not None
    assert "Using stale cached stats" in payload["message"]


def test_player_season_summary_aggregates_2025_stats_and_generates_news(client, db_session):
    create_response = client.post(
        "/players",
        json=[
            {
                "external_id": "3003",
                "name": "Summary Runner",
                "position": "RB",
                "school": "Texas",
            }
        ],
    )
    assert create_response.status_code == 201
    player_id = create_response.json()[0]["id"]

    db_session.add(
        PlayerStat(
            player_id=player_id,
            season=2025,
            week=1,
            source="sportsdata",
            stats={
                "RushingAttempts": 20,
                "RushingYards": 120,
                "RushingTouchdowns": 2,
                "Receptions": 3,
                "ReceivingYards": 25,
                "ReceivingTouchdowns": 0,
            },
        )
    )
    db_session.add(
        PlayerStat(
            player_id=player_id,
            season=2025,
            week=2,
            source="sportsdata",
            stats={
                "RushingAttempts": 18,
                "RushingYards": 95,
                "RushingTouchdowns": 1,
                "Receptions": 5,
                "ReceivingYards": 42,
                "ReceivingTouchdowns": 1,
            },
        )
    )
    db_session.commit()

    response = client.get(f"/players/{player_id}/season-summary?season=2025")
    assert response.status_code == 200
    payload = response.json()
    assert payload["player_id"] == player_id
    assert payload["season"] == 2025
    assert payload["source"] == "sportsdata_cached"
    assert payload["totals"]["games"] == 2
    assert payload["totals"]["rushing_yards"] == 215.0
    assert payload["totals"]["rushing_tds"] == 3.0
    assert payload["totals"]["receptions"] == 8.0
    assert payload["totals"]["receiving_yards"] == 67.0
    assert payload["totals"]["receiving_tds"] == 1.0
    assert payload["totals"]["fantasy_points"] > 0
    assert "Summary Runner" in payload["latest_news"]


def test_standings_endpoint_uses_db_snapshot_cache(client, db_session, monkeypatch):
    calls = {"count": 0}

    def fake_sync_standings(db, *, season: int, conference: str):
        calls["count"] += 1
        return upsert_power4_standings_snapshot(
            db,
            season=season,
            conference=conference,
            rows={
                "Alabama": {
                    "conference_rank": 1,
                    "conference_wins": 8,
                    "conference_losses": 0,
                    "overall_wins": 12,
                    "overall_losses": 1,
                },
                "Texas": {
                    "conference_rank": 2,
                    "conference_wins": 7,
                    "conference_losses": 1,
                    "overall_wins": 11,
                    "overall_losses": 2,
                },
            },
            source="sportsdata",
        )

    monkeypatch.setattr(stats_routes, "sync_power4_standings_from_sportsdata", fake_sync_standings)

    first = client.get("/stats/standings?season=2025&conference=SEC")
    assert first.status_code == 200
    first_payload = first.json()
    assert first_payload["total"] == 16
    assert first_payload["data"][0]["team"] == "Alabama"
    assert first_payload["data"][0]["conference_rank"] == 1
    assert calls["count"] == 1

    provider_state = (
        db_session.query(ProviderSyncState)
        .filter(
            ProviderSyncState.provider == "sportsdata",
            ProviderSyncState.feed == "standings_conference",
        )
        .first()
    )
    assert provider_state is not None
    assert provider_state.status == "ready"
    assert provider_state.expires_at is not None

    def fail_if_called(*args, **kwargs):
        raise AssertionError("Standings provider sync should not run while cache is fresh")

    monkeypatch.setattr(stats_routes, "sync_power4_standings_from_sportsdata", fail_if_called)

    second = client.get("/stats/standings?season=2025&conference=SEC")
    assert second.status_code == 200
    second_payload = second.json()
    assert second_payload["data"][0]["team"] == "Alabama"
    assert second_payload["data"][0]["conference_rank"] == 1
    assert calls["count"] == 1


def test_injuries_endpoint_uses_cached_db_rows_when_feed_is_fresh(client, db_session, monkeypatch):
    calls = {"count": 0}

    def fake_sync_injuries(db, *, season: int, week: int, conference: str | None = None):
        calls["count"] += 1
        player = db.query(Player).filter(Player.name == "Cache Injury").first()
        if not player:
            player = Player(
                external_id="injury-cache-1",
                name="Cache Injury",
                school="Alabama",
                position="QB",
            )
            db.add(player)
            db.flush()

        injury = (
            db.query(Injury)
            .filter(
                Injury.player_id == player.id,
                Injury.season == season,
                Injury.week == week,
            )
            .first()
        )
        if not injury:
            injury = Injury(
                player_id=player.id,
                season=season,
                week=week,
                status="QUESTIONABLE",
                injury="Ankle",
                return_timeline="Day-to-day",
                practice_level="Limited",
                notes="Cached injury sync",
                is_game_time_decision=True,
                is_returning=False,
            )
        else:
            injury.status = "QUESTIONABLE"
            injury.injury = "Ankle"
        db.add(injury)
        return {"created": 1, "updated": 0, "removed": 0, "source": "rotowire", "rows_seen": 1}

    monkeypatch.setattr(stats_routes, "sync_power4_injuries", fake_sync_injuries)

    first = client.get("/stats/injuries?season=2025&week=1&conference=SEC")
    assert first.status_code == 200
    first_payload = first.json()
    assert first_payload["total"] == 1
    assert first_payload["data"][0]["player_name"] == "Cache Injury"
    assert first_payload["data"][0]["status"] == "QUESTIONABLE"
    assert calls["count"] == 1

    provider_state = (
        db_session.query(ProviderSyncState)
        .filter(
            ProviderSyncState.provider == "sportsdata",
            ProviderSyncState.feed == "injuries_week",
        )
        .first()
    )
    assert provider_state is not None
    assert provider_state.status == "ready"
    assert provider_state.expires_at is not None

    def fail_if_called(*args, **kwargs):
        raise AssertionError("Injury feed sync should not rerun while cache is fresh")

    monkeypatch.setattr(stats_routes, "sync_power4_injuries", fail_if_called)

    second = client.get("/stats/injuries?season=2025&week=1&conference=SEC")
    assert second.status_code == 200
    second_payload = second.json()
    assert second_payload["total"] == 1
    assert second_payload["data"][0]["player_name"] == "Cache Injury"
    assert calls["count"] == 1
