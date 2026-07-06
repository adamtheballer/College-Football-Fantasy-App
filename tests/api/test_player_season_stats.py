from collegefootballfantasy_api.app.api.routes import players as players_route
from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.models.injury import Injury
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_stat import PlayerStat


def test_player_season_stats_returns_cached_week_zero_stats(client, db_session):
    player = Player(
        name="Cached Runner",
        position="RB",
        school="Georgia",
        external_id="123",
    )
    db_session.add(player)
    db_session.flush()
    db_session.add(
        PlayerStat(
            player_id=player.id,
            season=2025,
            week=0,
            source="sportsdata",
            stats={"RushingYards": 1100, "RushingTouchdowns": 12},
        )
    )
    db_session.commit()

    response = client.get(f"/players/{player.id}/season-stats", params={"season": 2025})

    assert response.status_code == 200
    body = response.json()
    assert body["player_id"] == player.id
    assert body["season"] == 2025
    assert body["week"] == 0
    assert body["cached"] is True
    assert body["stats"]["RushingYards"] == 1100


def test_player_season_stats_missing_sportsdata_key_returns_nullable_response(
    client, db_session, monkeypatch
):
    monkeypatch.setattr(settings, "sportsdata_api_key", None)
    player = Player(
        name="No Key Player",
        position="WR",
        school="Ohio State",
        external_id="999",
    )
    db_session.add(player)
    db_session.commit()

    response = client.get(f"/players/{player.id}/season-stats", params={"season": 2025})

    assert response.status_code == 200
    body = response.json()
    assert body["stats"] is None
    assert body["cached"] is False
    assert "SPORTSDATA_API_KEY" in body["message"]


def test_player_season_stats_missing_external_id_returns_nullable_response(
    client, db_session, monkeypatch
):
    monkeypatch.setattr(settings, "sportsdata_api_key", "fake-key")
    player = Player(
        name="No External Id",
        position="TE",
        school="Iowa",
        external_id=None,
    )
    db_session.add(player)
    db_session.commit()

    response = client.get(f"/players/{player.id}/season-stats", params={"season": 2025})

    assert response.status_code == 200
    body = response.json()
    assert body["stats"] is None
    assert body["cached"] is False
    assert "external_id" in body["message"]


def test_player_season_stats_missing_provider_data_returns_nullable_response(
    client, db_session, monkeypatch
):
    monkeypatch.setattr(settings, "sportsdata_api_key", "fake-key")

    class EmptySportsDataClient:
        def get_player_stats(self, external_id):
            return {}

    monkeypatch.setattr(players_route, "SportsDataClient", EmptySportsDataClient)
    player = Player(
        name="No Provider Data",
        position="QB",
        school="Texas",
        external_id="404",
    )
    db_session.add(player)
    db_session.commit()

    response = client.get(f"/players/{player.id}/season-stats", params={"season": 2025})

    assert response.status_code == 200
    body = response.json()
    assert body["stats"] is None
    assert body["cached"] is False
    assert "No season stats returned" in body["message"]


def test_player_card_returns_espn_about_injury_history_and_cached_stats(client, db_session, monkeypatch):
    class FakeESPNClient:
        def get_athlete_profile(self, espn_player_id):
            assert espn_player_id == "4801299"
            return {
                "athlete": {
                    "id": "4801299",
                    "displayHeight": "6' 1\"",
                    "displayWeight": "210 lbs",
                    "jersey": "3",
                    "status": {"name": "Active"},
                    "position": {"displayName": "Quarterback"},
                    "team": {"displayName": "Iowa State Cyclones"},
                    "headshot": {"href": "https://example.com/headshot.png"},
                    "birthPlace": {"city": "Tampa", "state": "FL", "country": "USA"},
                }
            }

    monkeypatch.setattr(players_route, "ESPNClient", FakeESPNClient)
    player = Player(
        name="Rocco Becht",
        position="QB",
        school="Iowa State",
        external_id="espn:4801299",
        player_class="JR",
    )
    db_session.add(player)
    db_session.flush()
    db_session.add_all(
        [
            Injury(
                player_id=player.id,
                season=2025,
                week=7,
                status="QUESTIONABLE",
                injury="Shoulder",
                return_timeline="Week-to-week",
                practice_level="Limited",
                notes="Left game early.",
            ),
            PlayerStat(
                player_id=player.id,
                season=2025,
                week=0,
                source="espn",
                stats={"PassingYards": 3200, "PassingTouchdowns": 25},
            ),
        ]
    )
    db_session.commit()

    response = client.get(f"/players/{player.id}/card")

    assert response.status_code == 200
    body = response.json()
    assert body["about"]["source"] == "espn"
    assert body["about"]["height"] == "6' 1\""
    assert body["about"]["weight"] == "210 lbs"
    assert body["about"]["birthplace"] == "Tampa, FL, USA"
    assert body["about"]["player_class"] == "JR"
    assert body["injuries"][0]["injury"] == "Shoulder"
    assert body["season_stats"][0]["stats"]["PassingYards"] == 3200
