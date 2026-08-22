from datetime import datetime, timezone

from collegefootballfantasy_api.app.models.player_trade_value import PlayerTradeValue
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.services.player_trade_value import IN_SEASON_VALUE_POLICY_VERSION
from collegefootballfantasy_api.app.services.weekly_outlook_refresh import (
    POSTGAME_PROJECTION_VERSION,
    refresh_post_final_outlook,
)
from tests.api.scoring_helpers import create_scoring_fixture


def _finalized_week_one_fixture(db_session):
    league, _home, _away, players, matchup = create_scoring_fixture(db_session)
    matchup.status = "final"
    db_session.add(
        TeamSchedule(
            team_name="Test",
            season=2026,
            week=2,
            opponent_name="Next Opponent",
            location="home",
            is_bye=False,
            neutral_site=False,
            conference_game=False,
            date_confirmed=True,
        )
    )
    for player in players.values():
        player.raw_cfb27_rating = 82
        player.cfb27_overall = 82
    db_session.commit()
    return league, players, matchup


def test_post_final_refresh_updates_next_week_and_values_only_after_every_matchup_is_final(db_session):
    _league, players, matchup = _finalized_week_one_fixture(db_session)

    waiting_matchup = matchup
    waiting_matchup.status = "live"
    db_session.commit()
    waiting = refresh_post_final_outlook(db_session, season=2026, completed_week=1)
    assert waiting == {"status": "waiting_for_finality", "projected_week": 2, "projections": 0, "values": 0}
    assert db_session.query(WeeklyProjection).filter_by(season=2026, week=2).count() == 0

    waiting_matchup.status = "final"
    db_session.commit()
    result = refresh_post_final_outlook(db_session, season=2026, completed_week=1)

    assert result["status"] == "refreshed"
    qb_projection = (
        db_session.query(WeeklyProjection)
        .filter_by(
            player_id=players["qb"].id,
            season=2026,
            week=2,
            projection_version=POSTGAME_PROJECTION_VERSION,
        )
        .one()
    )
    assert qb_projection.is_published is True
    assert qb_projection.baseline_source == "verified_week_1_stats"
    assert qb_projection.baseline_games_played == 1
    assert qb_projection.model_version == "postgame_espn_v1"
    assert qb_projection.fantasy_points >= 0
    value = (
        db_session.query(PlayerTradeValue)
        .filter_by(
            player_id=players["qb"].id,
            season=2026,
            week=1,
            policy_version=IN_SEASON_VALUE_POLICY_VERSION,
        )
        .one()
    )
    assert value.value >= 0


def test_post_final_refresh_preserves_a_locked_next_week_projection(db_session):
    _league, players, _matchup = _finalized_week_one_fixture(db_session)
    locked_at = datetime(2026, 9, 5, tzinfo=timezone.utc)
    db_session.add(
        WeeklyProjection(
            player_id=players["qb"].id,
            season=2026,
            week=2,
            projection_version=POSTGAME_PROJECTION_VERSION,
            is_published=True,
            locked_at=locked_at,
            fantasy_points=17.3,
            baseline_source="locked_live_game",
        )
    )
    db_session.commit()

    result = refresh_post_final_outlook(db_session, season=2026, completed_week=1)

    assert result["status"] == "refreshed"
    locked = (
        db_session.query(WeeklyProjection)
        .filter_by(
            player_id=players["qb"].id,
            season=2026,
            week=2,
            projection_version=POSTGAME_PROJECTION_VERSION,
        )
        .one()
    )
    assert locked.locked_at is not None
    # SQLite returns naive datetimes while PostgreSQL retains UTC tzinfo for
    # this timezone-aware column. The stored instant must be identical.
    assert locked.locked_at.replace(tzinfo=timezone.utc) == locked_at
    assert locked.fantasy_points == 17.3
    assert locked.baseline_source == "locked_live_game"
