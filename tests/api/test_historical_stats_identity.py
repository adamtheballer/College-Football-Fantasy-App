from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.services import historical_stats
from collegefootballfantasy_api.app.services.historical_stats import legacy_espn_player_id


def test_legacy_espn_player_id_accepts_explicit_espn_ids():
    assert legacy_espn_player_id("espn:12345") == "12345"
    assert legacy_espn_player_id("12345") == "12345"


def test_legacy_espn_player_id_rejects_non_espn_external_ids():
    assert legacy_espn_player_id("cfb27:jeremiahsmith|ohio-state|wr") is None
    assert legacy_espn_player_id("sportsdata:9988") is None


def test_explicit_import_override_bypasses_only_the_feature_flag(monkeypatch):
    player = Player(id=1, name="Dante Moore", school="Oregon", position="QB")
    monkeypatch.setattr(historical_stats.settings, "espn_historical_stats_enabled", False)
    monkeypatch.setattr(historical_stats, "resolve_espn_player_id", lambda _db, _player: None)

    default_response = historical_stats.fetch_and_store_player_history(object(), player)
    override_response = historical_stats.fetch_and_store_player_history(object(), player, allow_disabled=True)

    assert default_response.status == "disabled"
    assert override_response.status == "no_provider_mapping"
