from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.provider_identity import PlayerProviderId
from collegefootballfantasy_api.app.services.espn_player_lookup import resolve_espn_player_identity_and_profile


def test_resolver_accepts_verified_middle_name_and_espn_place_kicker_alias(db_session, monkeypatch):
    monkeypatch.setattr(settings, "player_headshots_enabled", True)
    player = Player(name="Jacobo Lozano", school="Purdue", position="K")
    db_session.add(player)
    db_session.commit()

    class FakeESPNClient:
        def search_players(self, query, *, limit=10):
            assert query == "Jacobo Lozano"
            return [
                {
                    "id": "5296700",
                    "displayName": "Jacobo Echeverria Lozano",
                    "type": "player",
                    "sport": "football",
                    "league": "college-football",
                }
            ]

        def get_athlete_profile(self, provider_player_id):
            assert provider_player_id == "5296700"
            return {
                "athlete": {
                    "id": provider_player_id,
                    "team": {"shortDisplayName": "Purdue"},
                    "position": {"abbreviation": "PK"},
                    "headshot": {"href": "https://a.espncdn.com/i/headshots/college-football/players/full/5296700.png"},
                }
            }

    result = resolve_espn_player_identity_and_profile(db_session, player, client=FakeESPNClient())

    assert result.outcome == "matched"
    mapping = db_session.query(PlayerProviderId).filter_by(player_id=player.id, provider="espn").one()
    assert mapping.provider_player_id == "5296700"
    assert player.espn_headshot_url.endswith("/5296700.png")


def test_resolver_accepts_the_canonical_michigan_state_school_alias(db_session, monkeypatch):
    monkeypatch.setattr(settings, "player_headshots_enabled", True)
    player = Player(name="Fredrick Moore", school="Michigan State", position="WR")
    db_session.add(player)
    db_session.commit()

    class FakeESPNClient:
        def search_players(self, _query, *, limit=10):
            return [
                {
                    "id": "4905609",
                    "displayName": "Fredrick Moore",
                    "type": "player",
                    "sport": "football",
                    "league": "college-football",
                }
            ]

        def get_athlete_profile(self, _provider_player_id):
            return {
                "athlete": {
                    "id": "4905609",
                    "team": {"shortDisplayName": "Michigan St"},
                    "position": {"abbreviation": "WR"},
                    "headshot": {"href": "https://a.espncdn.com/i/headshots/college-football/players/full/4905609.png"},
                }
            }

    result = resolve_espn_player_identity_and_profile(db_session, player, client=FakeESPNClient())

    assert result.outcome == "matched"
    assert player.espn_headshot_url.endswith("/4905609.png")
