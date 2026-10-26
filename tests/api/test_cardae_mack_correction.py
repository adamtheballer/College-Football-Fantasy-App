from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_game_stat import PlayerGameStat
from collegefootballfantasy_api.app.models.player_role_snapshot import PlayerRoleSnapshot
from collegefootballfantasy_api.app.models.provider_identity import PlayerProviderId
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.services.cardae_mack_correction import apply_cardae_mack_correction
from collegefootballfantasy_api.app.services.player_pool_filters import canonical_fantasy_player_filter
from scripts.apply_cardae_mack_asu_correction import role_baselines


def evidence():
    return {"athlete": {"id": "5209382", "displayName": "Cardae Mack", "team": {"id": "9"},
        "position": {"abbreviation": "RB"}, "displayHeight": "5' 10\"", "displayWeight": "215 lbs",
        "displayExperience": "Freshman", "jersey": "25", "birthPlace": {"city": "Houston", "state": "TX", "country": "USA"}}}


def summary():
    return {"header": {"id": "401856839", "competitions": [{"status": {"type": {"completed": True}}}]},
        "boxscore": {"players": [{"team": {"location": "Arizona State", "displayName": "Arizona State Sun Devils"},
            "statistics": [{"name": "rushing", "keys": ["rushingAttempts", "rushingYards", "yardsPerRushAttempt", "rushingTouchdowns"],
                "athletes": [{"athlete": {"id": "5209382", "displayName": "Cardae Mack"}, "stats": ["26", "159", "6.1", "4"]}]}]}]}}


def setup_asu(db):
    players = [Player(name=name, school="Arizona State", position="RB", depth_order=n,
        depth_chart_position=f"RB{n}", sheet_source_sheet_id="canonical-preseason:2026:test", sheet_projected_season_points=100,
        raw_cfb27_rating=78) for n, name in enumerate(("Kyson Brown", "Demarius Robinson", "Jason Brown Jr."), 1)]
    game = Game(external_id="401856839", season=2026, week=8, home_team="Arizona State", away_team="Kansas State", schedule_status="final")
    db.add_all([*players, game]); db.flush()
    db.add(PlayerGameStat(player_id=players[2].id, game_id=game.id, season=2026, week=8, source="espn_final_boxscore", stats={"rush_yards": 10}))
    db.commit()
    return players


def apply(db, **kwargs):
    return apply_cardae_mack_correction(db, season=2026, effective_week=8, profile=kwargs.get("profile", evidence()),
        summaries=kwargs.get("summaries", [summary()]), role_baselines=role_baselines())


def test_asu_replacement_is_exact_idempotent_and_preserves_displaced_history(db_session):
    players = setup_asu(db_session)
    result = apply(db_session); db_session.commit()
    mack = db_session.get(Player, result["player_id"])
    assert [(r["name"], r["slot"]) for r in result["active_depth"]] == [("Kyson Brown", "RB1"), ("Cardae Mack", "RB2"), ("Demarius Robinson", "RB3")]
    assert mack.player_class == "Freshman" and mack.espn_jersey == "25"
    assert (mack.espn_height_inches, mack.espn_weight, mack.espn_birthplace) == (70, "215 lbs", "Houston, TX, USA")
    assert mack.raw_cfb27_rating is None  # Never copy the displaced player's game rating.
    assert mack.sheet_projected_season_points == 152.6
    assert db_session.get(Player, players[1].id).sheet_projected_season_points == 67.8
    assert {p.name for p in db_session.scalars(select(Player).where(canonical_fantasy_player_filter(2026)))} == {"Kyson Brown", "Cardae Mack", "Demarius Robinson"}
    assert db_session.get(Player, players[2].id) is not None
    assert db_session.query(PlayerGameStat).filter_by(player_id=players[2].id).one().stats == {"rush_yards": 10}
    stat = db_session.query(PlayerGameStat).filter_by(player_id=mack.id).one()
    assert (stat.stats["rush_yards"], stat.stats["rush_tds"]) == (159, 4)
    assert apply(db_session)["player_id"] == mack.id
    db_session.commit()
    assert db_session.query(Player).count() == 4
    assert db_session.query(PlayerRoleSnapshot).count() == 18
    assert db_session.query(PlayerProviderId).filter_by(player_id=mack.id, provider="espn").count() == 1
    assert db_session.query(PlayerGameStat).filter_by(player_id=mack.id).count() == 1
    assert mack.sheet_projected_season_points == 152.6


@pytest.mark.parametrize("change", ["id", "team", "position"])
def test_wrong_provider_identity_cannot_modify_the_catalog(db_session, change):
    setup_asu(db_session)
    profile = evidence()
    profile["athlete"][change] = {"id": "158"} if change == "team" else {"abbreviation": "WR"} if change == "position" else "not-mack"
    with pytest.raises(ValueError, match="Profile must verify"):
        apply(db_session, profile=profile)
    assert db_session.query(Player).count() == 3


def test_unfinished_game_cannot_be_imported_as_completed_history(db_session):
    setup_asu(db_session)
    payload = summary(); payload["header"]["competitions"][0]["status"]["type"]["completed"] = False
    with pytest.raises(ValueError, match="accepted completed game"):
        apply(db_session, summaries=[payload])
    assert db_session.query(Player).count() == 3


def test_locked_future_projection_rolls_back_the_entire_correction(db_session):
    players = setup_asu(db_session)
    db_session.add(WeeklyProjection(player_id=players[1].id, season=2026, week=9, fantasy_points=12,
        is_published=True, locked_at=datetime.now(timezone.utc)))
    db_session.commit()
    with pytest.raises(ValueError, match="locked Week 9"):
        apply(db_session)
    db_session.rollback()
    assert db_session.query(Player).count() == 3
    assert db_session.get(Player, players[1].id).depth_order == 2
    assert db_session.query(WeeklyProjection).one().fantasy_points == 12
