import pytest

from collegefootballfantasy_api.app.models.lineup_week_snapshot import LineupWeekSnapshot
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.player_week_score import PlayerWeekScore
from collegefootballfantasy_api.app.models.scoring_run import ScoringRun
from collegefootballfantasy_api.app.models.team_week_score import TeamWeekScore
from collegefootballfantasy_api.app.services.scoring_service import (
    recalculate_league_week_scores,
    run_league_scoring_recalculation,
)
from tests.api.scoring_helpers import create_scoring_fixture


def test_recalculate_league_week_scores_is_idempotent_and_sums_starters_only(client, db_session):
    league, home, _away, players, _matchup = create_scoring_fixture(db_session)

    first = recalculate_league_week_scores(db_session, league.id, 2026, 1)
    second = recalculate_league_week_scores(db_session, league.id, 2026, 1)
    db_session.commit()

    assert first.players_scored == second.players_scored == 7
    assert db_session.query(LineupWeekSnapshot).filter_by(league_id=league.id, season=2026, week=1).count() == 6
    available_score = db_session.query(PlayerWeekScore).filter_by(league_id=league.id, player_id=players["available"].id, season=2026, week=1).one()
    assert available_score.fantasy_points == 0.0

    home_score = db_session.query(TeamWeekScore).filter_by(league_id=league.id, team_id=home.id, season=2026, week=1).one()
    assert home_score.starter_points == 56.0
    assert home_score.bench_points == 32.0
    assert home_score.total_points == 56.0
    assert any(row["player_id"] == players["bench"].id for row in home_score.breakdown_json["players"])


def test_stat_correction_changes_scores_without_incrementing(client, db_session):
    league, home, _away, players, _matchup = create_scoring_fixture(db_session)
    recalculate_league_week_scores(db_session, league.id, 2026, 1)

    stat = db_session.query(PlayerStat).filter_by(player_id=players["qb"].id, season=2026, week=1).one()
    stat.stats = {"PassingYards": 300, "PassingTouchdowns": 4}
    recalculate_league_week_scores(db_session, league.id, 2026, 1)
    db_session.commit()

    qb_score = db_session.query(PlayerWeekScore).filter_by(league_id=league.id, player_id=players["qb"].id, season=2026, week=1).one()
    home_score = db_session.query(TeamWeekScore).filter_by(league_id=league.id, team_id=home.id, season=2026, week=1).one()
    assert qb_score.fantasy_points == 28.0
    assert home_score.total_points == 68.0


def test_scoring_run_records_success_and_failure(client, db_session):
    league, *_ = create_scoring_fixture(db_session)
    summary = run_league_scoring_recalculation(db_session, league.id, 2026, 1)

    assert summary.players_scored == 7
    success_run = db_session.query(ScoringRun).filter_by(league_id=league.id, status="success").one()
    assert success_run.players_updated == 7

    with pytest.raises(Exception):
        run_league_scoring_recalculation(db_session, league.id + 999, 2026, 1)
    failed_run = db_session.query(ScoringRun).filter_by(league_id=league.id + 999, status="failed").one()
    assert failed_run.error_message
