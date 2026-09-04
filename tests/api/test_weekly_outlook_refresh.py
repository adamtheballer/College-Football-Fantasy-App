from datetime import datetime, timezone

from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.player_game_stat import PlayerGameStat
from collegefootballfantasy_api.app.models.player_trade_value import PlayerTradeValue
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.services.player_trade_value import IN_SEASON_VALUE_POLICY_VERSION
from collegefootballfantasy_api.app.services.weekly_outlook_refresh import (
    POSTGAME_PROJECTION_VERSION,
    performance_residual_adjustment,
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
    assert qb_projection.model_version == "postgame_espn_v2"
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


def test_week_zero_final_updates_only_affected_players_week_one_outlook_without_league_scoring(db_session):
    league, _home, _away, players, matchup = create_scoring_fixture(db_session)
    week_zero_game = Game(
        external_id="usc-week-zero", season=2026, week=0,
        home_team="Test", away_team="Early Opponent", home_points=28, away_points=14,
    )
    db_session.add(week_zero_game)
    db_session.flush()
    db_session.add_all([
        TeamSchedule(
            team_name="Test", season=2026, week=0, game_id=week_zero_game.id,
            opponent_name="Early Opponent", location="home", is_bye=False,
            neutral_site=False, conference_game=False, date_confirmed=True,
        ),
        TeamSchedule(
            team_name="Test", season=2026, week=1,
            opponent_name="Week One Opponent", location="away", is_bye=False,
            neutral_site=False, conference_game=False, date_confirmed=True,
        ),
        PlayerGameStat(
            player_id=players["qb"].id, game_id=week_zero_game.id, season=2026, week=0,
            source="espn_final_boxscore", stats={"PassingYards": 280, "PassingTouchdowns": 3},
        ),
        PlayerStat(
            player_id=players["qb"].id, season=2026, week=0, source="espn_final_boxscore",
            stats={"PassingYards": 280, "PassingTouchdowns": 3},
        ),
    ])
    db_session.commit()

    result = refresh_post_final_outlook(db_session, season=2026, completed_week=0)

    assert result["status"] == "refreshed"
    projection = db_session.query(WeeklyProjection).filter_by(
        player_id=players["qb"].id,
        season=2026,
        week=1,
        projection_version=POSTGAME_PROJECTION_VERSION,
    ).one()
    assert projection.baseline_source == "verified_week_0_stats"
    assert projection.baseline_games_played == 1
    assert db_session.query(PlayerTradeValue).filter_by(season=2026, week=0).count() == 0
    assert matchup.status == "scheduled"


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


def test_post_final_refresh_weighs_a_certified_projection_miss_into_the_next_week(db_session):
    _league, players, _matchup = _finalized_week_one_fixture(db_session)
    underperformer = players["qb"]
    on_projection = players["away_qb"]
    underperformer_stat = (
        db_session.query(PlayerStat)
        .filter_by(player_id=underperformer.id, season=2026, week=1)
        .one()
    )
    on_projection_stat = (
        db_session.query(PlayerStat)
        .filter_by(player_id=on_projection.id, season=2026, week=1)
        .one()
    )
    underperformer_stat.stats = {"fantasy_points": 6.0}
    on_projection_stat.stats = {"fantasy_points": 20.0}
    db_session.add_all(
        [
            WeeklyProjection(
                player_id=underperformer.id,
                season=2026,
                week=1,
                projection_version="PRESEASON",
                is_published=True,
                fantasy_points=20.0,
            ),
            WeeklyProjection(
                player_id=on_projection.id,
                season=2026,
                week=1,
                projection_version="PRESEASON",
                is_published=True,
                fantasy_points=20.0,
            ),
        ]
    )
    db_session.commit()

    result = refresh_post_final_outlook(db_session, season=2026, completed_week=1)
    assert result["status"] == "refreshed"
    refreshed = {
        row.player_id: row
        for row in db_session.query(WeeklyProjection).filter_by(
            season=2026,
            week=2,
            projection_version=POSTGAME_PROJECTION_VERSION,
        )
    }

    assert refreshed[underperformer.id].fantasy_points < refreshed[on_projection.id].fantasy_points
    assert refreshed[underperformer.id].floor <= refreshed[underperformer.id].fantasy_points
    assert refreshed[underperformer.id].ceiling >= refreshed[underperformer.id].fantasy_points


def test_performance_residual_adjustment_is_weighted_and_bounded():
    assert performance_residual_adjustment(
        actual_points=6.0,
        projected_points=20.0,
        next_week_baseline=18.0,
    ) == -3.08
    assert performance_residual_adjustment(
        actual_points=100.0,
        projected_points=20.0,
        next_week_baseline=18.0,
    ) == 3.3
