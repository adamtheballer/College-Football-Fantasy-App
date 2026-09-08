from sqlalchemy import select

from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_game_stat import PlayerGameStat
from collegefootballfantasy_api.app.models.player_role_snapshot import PlayerRoleSnapshot
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.provider_identity import PlayerProviderId
from collegefootballfantasy_api.app.services.jamal_rule_correction import (
    JAMAL_RULE_ESPN_ID,
    NEBRASKA_WEEK_ONE_EVENT_ID,
    apply_jamal_rule_nebraska_correction,
)
from collegefootballfantasy_api.app.services.player_pool_filters import (
    canonical_fantasy_player_filter,
)


def _profile():
    return {
        "athlete": {
            "id": JAMAL_RULE_ESPN_ID,
            "displayName": "Jamal Rule",
            "displayHeight": "6' 0\"",
            "displayWeight": "215 lbs",
            "jersey": "25",
            "birthPlace": {"city": "Salisbury", "state": "NC", "country": "USA"},
            "team": {"location": "Nebraska", "displayName": "Nebraska Cornhuskers"},
            "position": {"abbreviation": "RB"},
            "status": {"name": "Active"},
        }
    }


def _summary():
    return {
        "header": {
            "id": NEBRASKA_WEEK_ONE_EVENT_ID,
            "competitions": [{"status": {"type": {"completed": True, "name": "STATUS_FINAL"}}}],
        },
        "boxscore": {
            "players": [{
                "team": {"location": "Nebraska", "displayName": "Nebraska Cornhuskers"},
                "statistics": [
                    {
                        "name": "rushing",
                        "keys": ["rushingAttempts", "rushingYards", "yardsPerRushAttempt", "rushingTouchdowns"],
                        "athletes": [{
                            "athlete": {"id": JAMAL_RULE_ESPN_ID, "displayName": "Jamal Rule"},
                            "stats": ["15", "122", "8.1", "2"],
                        }],
                    },
                    {
                        "name": "receiving",
                        "keys": ["receptions", "receivingYards", "yardsPerReception", "receivingTouchdowns"],
                        "athletes": [{
                            "athlete": {"id": JAMAL_RULE_ESPN_ID, "displayName": "Jamal Rule"},
                            "stats": ["2", "47", "23.5", "1"],
                        }],
                    },
                ],
            }],
        },
    }


def _rb(name: str, depth: int, source: str = "canonical-preseason:2026:fixture") -> Player:
    return Player(
        name=name,
        school="Nebraska",
        position="RB",
        depth_chart_position=f"RB{depth}",
        depth_order=depth,
        sheet_source_sheet_id=source,
        sheet_projected_season_points=100.0,
    )


def test_jamal_rule_correction_adds_verified_player_history_and_reorders_nebraska_rbs(db_session):
    mozee = _rb("Isaiah Mozee", 1)
    nelson = _rb("Mekhi Nelson", 2)
    ives = _rb("Kwinten Ives", 3)
    game = Game(
        external_id=NEBRASKA_WEEK_ONE_EVENT_ID,
        season=2026,
        week=1,
        home_team="Nebraska",
        away_team="Ohio",
        schedule_status="final",
    )
    db_session.add_all([mozee, nelson, ives, game])
    db_session.commit()

    result = apply_jamal_rule_nebraska_correction(
        db_session,
        season=2026,
        role_weeks=(1, 2),
        profile=_profile(),
        week_one_summary=_summary(),
    )
    db_session.commit()

    rule = db_session.scalar(select(Player).where(Player.name == "Jamal Rule"))
    assert rule is not None
    assert result["week_one_fantasy_points"] == 36.9
    assert rule.external_id == f"espn:{JAMAL_RULE_ESPN_ID}"
    assert rule.espn_height == "6' 0\""
    assert rule.espn_weight == "215 lbs"
    assert rule.espn_birthplace == "Salisbury, NC, USA"
    assert rule.depth_chart_position == "RB1"
    assert rule.depth_order == 1
    assert rule.sheet_projected_season_points and rule.sheet_projected_season_points > 0
    assert db_session.scalar(
        select(PlayerProviderId).where(
            PlayerProviderId.player_id == rule.id,
            PlayerProviderId.provider == "espn",
            PlayerProviderId.provider_player_id == JAMAL_RULE_ESPN_ID,
            PlayerProviderId.verification_status == "verified",
        )
    ) is not None

    assert (mozee.depth_chart_position, mozee.depth_order) == ("RB2", 2)
    assert (nelson.depth_chart_position, nelson.depth_order) == ("RB3", 3)
    assert (ives.depth_chart_position, ives.depth_order) == (None, None)
    assert ives.sheet_source_sheet_id.startswith("legacy-canonical-preseason:2026:")
    active_names = {
        player.name
        for player in db_session.scalars(select(Player).where(canonical_fantasy_player_filter(2026))).all()
    }
    assert {"Jamal Rule", "Isaiah Mozee", "Mekhi Nelson"}.issubset(active_names)
    assert "Kwinten Ives" not in active_names

    weekly = db_session.scalar(select(PlayerStat).where(PlayerStat.player_id == rule.id, PlayerStat.week == 1))
    game_stat = db_session.scalar(select(PlayerGameStat).where(PlayerGameStat.player_id == rule.id, PlayerGameStat.game_id == game.id))
    assert weekly is not None and weekly.verified is True and weekly.source == "espn_final_boxscore"
    assert game_stat is not None and game_stat.source == "espn_final_boxscore"
    assert game_stat.stats["rush_yards"] == 122.0
    assert game_stat.stats["rec_tds"] == 1.0

    # Re-applying must replace the exact verified rows, not add a second player
    # or double the completed Week 1 performance.
    apply_jamal_rule_nebraska_correction(
        db_session,
        season=2026,
        role_weeks=(1, 2),
        profile=_profile(),
        week_one_summary=_summary(),
    )
    db_session.commit()
    assert db_session.query(Player).filter_by(name="Jamal Rule", school="Nebraska", position="RB").count() == 1
    assert db_session.query(PlayerGameStat).filter_by(player_id=rule.id, game_id=game.id).count() == 1
    assert db_session.query(PlayerRoleSnapshot).filter_by(player_id=rule.id, season=2026).count() == 2
