from sqlalchemy import select

from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_game_stat import PlayerGameStat
from collegefootballfantasy_api.app.models.player_role_snapshot import PlayerRoleSnapshot
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.provider_identity import PlayerProviderId
from collegefootballfantasy_api.app.services.legend_bey_correction import (
    LEGEND_BEY_ESPN_ID,
    OHIO_STATE_WEEK_ONE_EVENT_ID,
    apply_legend_bey_ohio_state_correction,
)
from collegefootballfantasy_api.app.services.player_pool_filters import canonical_fantasy_player_filter


def _profile():
    return {
        "athlete": {
            "id": LEGEND_BEY_ESPN_ID,
            "displayName": "Legend Bey",
            "displayHeight": "5' 10\"",
            "displayWeight": "195 lbs",
            "jersey": "2",
            "birthPlace": {"city": "Forney", "state": "TX", "country": "USA"},
            "team": {"location": "Ohio State", "displayName": "Ohio State Buckeyes"},
            "position": {"abbreviation": "RB"},
            "status": {"name": "Active"},
        }
    }


def _summary():
    return {
        "header": {
            "id": OHIO_STATE_WEEK_ONE_EVENT_ID,
            "competitions": [{"status": {"type": {"completed": True, "name": "STATUS_FINAL"}}}],
        },
        "boxscore": {
            "players": [{
                "team": {"location": "Ohio State", "displayName": "Ohio State Buckeyes"},
                "statistics": [
                    {
                        "name": "rushing",
                        "keys": ["rushingAttempts", "rushingYards", "yardsPerRushAttempt", "rushingTouchdowns"],
                        "athletes": [{
                            "athlete": {"id": LEGEND_BEY_ESPN_ID, "displayName": "Legend Bey"},
                            "stats": ["6", "37", "6.2", "0"],
                        }],
                    },
                    {
                        "name": "receiving",
                        "keys": ["receptions", "receivingYards", "yardsPerReception", "receivingTouchdowns"],
                        "athletes": [{
                            "athlete": {"id": LEGEND_BEY_ESPN_ID, "displayName": "Legend Bey"},
                            "stats": ["2", "37", "18.5", "1"],
                        }],
                    },
                ],
            }],
        },
    }


def _rb(name: str, depth: int) -> Player:
    return Player(
        name=name,
        school="Ohio State",
        position="RB",
        depth_chart_position=f"RB{depth}",
        depth_order=depth,
        sheet_source_sheet_id="canonical-preseason:2026:fixture",
        sheet_projected_season_points=100.0,
    )


def test_legend_bey_replaces_obsolete_ohio_state_rb3_with_verified_history(db_session):
    bo = _rb("Bo Jackson", 1)
    west = _rb("Isaiah West", 2)
    obsolete = _rb("Ja'Kobi Jackson", 3)
    game = Game(
        external_id=OHIO_STATE_WEEK_ONE_EVENT_ID,
        season=2026,
        week=1,
        home_team="Ohio State",
        away_team="Ball State",
        schedule_status="final",
    )
    db_session.add_all([bo, west, obsolete, game])
    db_session.commit()

    result = apply_legend_bey_ohio_state_correction(
        db_session,
        season=2026,
        role_weeks=(1, 2),
        profile=_profile(),
        week_one_summary=_summary(),
    )
    db_session.commit()

    bey = db_session.scalar(select(Player).where(Player.name == "Legend Bey"))
    assert bey is not None
    assert result["deleted_obsolete_player"] == "Ja'Kobi Jackson"
    assert result["week_one_fantasy_points"] == 15.4
    assert db_session.scalar(select(Player).where(Player.name == "Ja'Kobi Jackson")) is None
    assert (bey.depth_chart_position, bey.depth_order) == ("RB3", 3)
    assert bey.external_id == f"espn:{LEGEND_BEY_ESPN_ID}"
    assert bey.espn_height == "5' 10\""
    assert bey.espn_weight == "195 lbs"
    assert bey.espn_birthplace == "Forney, TX, USA"
    assert bey.sheet_projected_season_points and bey.sheet_projected_season_points > 0
    assert db_session.scalar(
        select(PlayerProviderId).where(
            PlayerProviderId.player_id == bey.id,
            PlayerProviderId.provider == "espn",
            PlayerProviderId.provider_player_id == LEGEND_BEY_ESPN_ID,
            PlayerProviderId.verification_status == "verified",
        )
    ) is not None

    active_names = {
        player.name
        for player in db_session.scalars(select(Player).where(canonical_fantasy_player_filter(2026))).all()
    }
    assert "Legend Bey" in active_names
    assert "Ja'Kobi Jackson" not in active_names

    weekly = db_session.scalar(select(PlayerStat).where(PlayerStat.player_id == bey.id, PlayerStat.week == 1))
    game_stat = db_session.scalar(select(PlayerGameStat).where(PlayerGameStat.player_id == bey.id, PlayerGameStat.game_id == game.id))
    assert weekly is not None and weekly.verified is True and weekly.source == "espn_final_boxscore"
    assert game_stat is not None and game_stat.source == "espn_final_boxscore"
    assert game_stat.stats["rush_yards"] == 37.0
    assert game_stat.stats["rec_tds"] == 1.0
    assert db_session.query(PlayerRoleSnapshot).filter_by(player_id=bey.id, season=2026).count() == 2

    # Re-applying must stay idempotent after the obsolete source row is gone.
    apply_legend_bey_ohio_state_correction(
        db_session,
        season=2026,
        role_weeks=(1, 2),
        profile=_profile(),
        week_one_summary=_summary(),
    )
    db_session.commit()
    assert db_session.query(Player).filter_by(name="Legend Bey", school="Ohio State", position="RB").count() == 1
    assert db_session.query(PlayerGameStat).filter_by(player_id=bey.id, game_id=game.id).count() == 1
