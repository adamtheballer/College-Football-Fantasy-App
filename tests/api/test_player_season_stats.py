from collegefootballfantasy_api.app.api.routes import players as players_route
from collegefootballfantasy_api.app.core.config import settings
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
