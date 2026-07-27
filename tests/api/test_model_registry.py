from collegefootballfantasy_api.app.db.base import Base
from collegefootballfantasy_api.app.db.model_registry import ensure_models_registered


def test_model_registry_includes_every_saturday_pick_table():
    ensure_models_registered()

    assert {
        "saturday_pick_contests",
        "saturday_pick_players",
        "saturday_pick_entries",
        "sponsor_reward_events",
    }.issubset(Base.metadata.tables)
