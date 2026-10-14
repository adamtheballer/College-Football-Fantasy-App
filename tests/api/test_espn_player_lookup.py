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


def test_reviewed_identity_variants_are_scoped_to_exact_catalog_and_provider_ids():
    from types import SimpleNamespace
    from collegefootballfantasy_api.app.services.espn_player_lookup import _item_name_matches,_position_matches,_school_matches
    from collegefootballfantasy_api.app.services.reviewed_espn_identities import _RECORDS
    for row in _RECORDS:
        player=SimpleNamespace(id=row['player_id'],name=row['catalog_name'],school=row['school'],position=row['catalog_position'])
        item={'id':row['provider_player_id'],'displayName':row['provider_names'][0]}
        profile={'athlete':{**item,'team':{'shortDisplayName':row['school']},'position':{'abbreviation':row['provider_positions'][0]}}}
        assert _item_name_matches(item,player) and _position_matches(profile,player) and _school_matches(profile,player)
        wrong_school={'athlete':{**profile['athlete'],'team':{'shortDisplayName':'Another School'}}}
        assert not _school_matches(wrong_school,player)
        if row['catalog_name']!=row['provider_names'][0]:
            assert not _item_name_matches({**item,'id':'999999'},player)
            assert not _item_name_matches(item,SimpleNamespace(**{**vars(player),'id':999999}))
        if row['catalog_position']!=row['provider_positions'][0]:
            wrong_id={'athlete':{**profile['athlete'],'id':'999999'}}
            assert not _position_matches(wrong_id,player)


def test_resolver_uses_reviewed_provider_candidate_without_loosening_other_names(db_session):
    player=Player(id=1241,name='Joshua Phifer',school='UCLA',position='TE');db_session.add(player);db_session.commit()
    class ReviewedClient:
        def search_players(self,*args,**kwargs):return []
        def get_athlete_profile(self,pid):
            return {'athlete':{'id':pid,'displayName':'Josh Phifer','team':{'shortDisplayName':'UCLA'},'position':{'abbreviation':'TE'}}}
    result=resolve_espn_player_identity_and_profile(db_session,player,client=ReviewedClient())
    assert result.outcome=='matched' and result.resolved.provider_player_id=='5084910'
