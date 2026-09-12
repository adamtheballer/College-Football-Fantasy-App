from sqlalchemy import select

from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_game_stat import PlayerGameStat
from collegefootballfantasy_api.app.models.player_role_snapshot import PlayerRoleSnapshot
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.provider_identity import PlayerProviderId
from collegefootballfantasy_api.app.services.javian_mallory_correction import (
    JAVIAN_MALLORY_ESPN_ID,
    MIAMI_WEEK_TWO_EVENT_ID,
    apply_javian_mallory_miami_correction,
)
from collegefootballfantasy_api.app.services.player_pool_filters import canonical_fantasy_player_filter


def _profile():
    return {
        "athlete": {
            "id": JAVIAN_MALLORY_ESPN_ID,
            "displayName": "Javian Mallory",
            "displayHeight": "5' 11\"",
            "displayWeight": "210 lbs",
            "displayExperience": "Freshman",
            "jersey": "21",
            "birthPlace": {"city": "Fort Lauderdale", "state": "FL", "country": "USA"},
            "team": {"location": "Miami", "displayName": "Miami Hurricanes"},
            "position": {"abbreviation": "RB"},
            "status": {"name": "Active"},
        }
    }


def _summary():
    return {
        "header": {
            "id": MIAMI_WEEK_TWO_EVENT_ID,
            "week": 2,
            "competitions": [{"status": {"type": {"completed": True, "name": "STATUS_FINAL"}}}],
        },
        "boxscore": {
            "players": [{
                "team": {"location": "Miami", "displayName": "Miami Hurricanes"},
                "statistics": [{
                    "name": "rushing",
                    "keys": ["rushingAttempts", "rushingYards", "yardsPerRushAttempt", "rushingTouchdowns"],
                    "athletes": [{
                        "athlete": {"id": JAVIAN_MALLORY_ESPN_ID, "displayName": "Javian Mallory"},
                        "stats": ["10", "142", "14.2", "2"],
                    }],
                }],
            }],
        },
    }


def _rb(name: str, depth: int) -> Player:
    return Player(
        name=name,
        school="Miami",
        position="RB",
        depth_chart_position=f"RB{depth}",
        depth_order=depth,
        sheet_source_sheet_id="canonical-preseason:2026:fixture",
        sheet_projected_season_points=100.0,
    )


def test_javian_mallory_correction_adds_verified_miami_rb3_and_retires_old_rb3(db_session):
    pringle = _rb("Girard Pringle Jr.", 3)
    game = Game(
        external_id=MIAMI_WEEK_TWO_EVENT_ID,
        season=2026,
        week=2,
        home_team="Miami",
        away_team="Florida A&M",
        schedule_status="final",
    )
    db_session.add_all([pringle, game])
    db_session.commit()

    result = apply_javian_mallory_miami_correction(
        db_session,
        season=2026,
        role_weeks=(2, 3),
        profile=_profile(),
        week_two_summary=_summary(),
    )
    db_session.commit()

    mallory = db_session.scalar(select(Player).where(Player.name == "Javian Mallory"))
    assert mallory is not None
    assert result["week_two_fantasy_points"] == 26.2
    assert mallory.external_id == f"espn:{JAVIAN_MALLORY_ESPN_ID}"
    assert mallory.espn_height == "5' 11\""
    assert mallory.espn_weight == "210 lbs"
    assert mallory.espn_birthplace == "Fort Lauderdale, FL, USA"
    assert mallory.player_class == "Freshman"
    assert (mallory.depth_chart_position, mallory.depth_order) == ("RB3", 3)
    assert mallory.sheet_projected_season_points and mallory.sheet_projected_season_points > 0
    assert db_session.scalar(
        select(PlayerProviderId).where(
            PlayerProviderId.player_id == mallory.id,
            PlayerProviderId.provider == "espn",
            PlayerProviderId.provider_player_id == JAVIAN_MALLORY_ESPN_ID,
            PlayerProviderId.verification_status == "verified",
        )
    ) is not None

    assert (pringle.depth_chart_position, pringle.depth_order) == (None, None)
    assert pringle.sheet_source_sheet_id.startswith("legacy-canonical-preseason:2026:")
    active_names = {
        player.name
        for player in db_session.scalars(select(Player).where(canonical_fantasy_player_filter(2026))).all()
    }
    assert "Javian Mallory" in active_names
    assert "Girard Pringle Jr." not in active_names

    weekly = db_session.scalar(select(PlayerStat).where(PlayerStat.player_id == mallory.id, PlayerStat.week == 2))
    game_stat = db_session.scalar(select(PlayerGameStat).where(PlayerGameStat.player_id == mallory.id, PlayerGameStat.game_id == game.id))
    assert weekly is not None and weekly.verified is True and weekly.source == "espn_final_boxscore"
    assert game_stat is not None and game_stat.source == "espn_final_boxscore"
    assert game_stat.stats["rush_yards"] == 142.0
    assert game_stat.stats["rush_tds"] == 2.0

    apply_javian_mallory_miami_correction(
        db_session,
        season=2026,
        role_weeks=(2, 3),
        profile=_profile(),
        week_two_summary=_summary(),
    )
    db_session.commit()
    assert db_session.query(Player).filter_by(name="Javian Mallory", school="Miami", position="RB").count() == 1
    assert db_session.query(PlayerGameStat).filter_by(player_id=mallory.id, game_id=game.id).count() == 1
    assert db_session.query(PlayerRoleSnapshot).filter_by(player_id=mallory.id, season=2026).count() == 2
