from collegefootballfantasy_api.app.db.base import Base
from collegefootballfantasy_api.app.db.model_registry import ensure_models_registered
from collegefootballfantasy_api.app.models.registry import load_all_models


def test_model_registry_includes_every_saturday_pick_table():
    ensure_models_registered()

    assert {
        "saturday_pick_contests",
        "saturday_pick_players",
        "saturday_pick_entries",
        "sponsor_reward_events",
    }.issubset(Base.metadata.tables)


def test_legacy_model_registry_delegates_to_the_canonical_registry():
    load_all_models()

    assert {
        "league_player_events",
        "player_trade_values",
        "saturday_pick_contests",
    }.issubset(Base.metadata.tables)
