import pytest

from collegefootballfantasy_api.app.models.lineup_week_snapshot import LineupWeekSnapshot
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.player_week_score import PlayerWeekScore
from collegefootballfantasy_api.app.models.scoring_run import ScoringRun
from collegefootballfantasy_api.app.models.team_week_score import TeamWeekScore
from collegefootballfantasy_api.app.services import scoring_service
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

    assert first.players_scored == second.players_scored == 6
    assert db_session.query(LineupWeekSnapshot).filter_by(league_id=league.id, season=2026, week=1).count() == 6
    available_score = db_session.query(PlayerWeekScore).filter_by(league_id=league.id, player_id=players["available"].id, season=2026, week=1).first()
    assert available_score is None

    home_score = db_session.query(TeamWeekScore).filter_by(league_id=league.id, team_id=home.id, season=2026, week=1).one()
    assert home_score.starter_points == 56.0
    assert home_score.bench_points == 32.0
    assert home_score.total_points == 56.0
    assert any(row["player_id"] == players["bench"].id for row in home_score.breakdown_json["players"])
    assert all(row["status"] == "live" for row in home_score.breakdown_json["players"] if row["player_id"] != players["ir"].id)


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

    assert summary.players_scored == 6
    success_run = db_session.query(ScoringRun).filter_by(league_id=league.id, status="success").one()
    assert success_run.players_updated == 6

    with pytest.raises(Exception):
        run_league_scoring_recalculation(db_session, league.id + 999, 2026, 1)
    failed_run = db_session.query(ScoringRun).filter_by(league_id=league.id + 999, status="failed").one()
    assert failed_run.error_message


def test_failed_scoring_run_rolls_back_partial_recalculation(client, db_session, monkeypatch):
    league, *_ = create_scoring_fixture(db_session)

    def fail_after_player_scores(*_args, **_kwargs):
        raise RuntimeError("team scoring exploded")

    monkeypatch.setattr(scoring_service, "recalculate_team_week_scores", fail_after_player_scores)

    with pytest.raises(RuntimeError, match="team scoring exploded"):
        run_league_scoring_recalculation(db_session, league.id, 2026, 1)

    failed_run = db_session.query(ScoringRun).filter_by(league_id=league.id, status="failed").one()
    assert failed_run.error_message == "team scoring exploded"
    assert db_session.query(LineupWeekSnapshot).filter_by(league_id=league.id, season=2026, week=1).count() == 0
    assert db_session.query(PlayerWeekScore).filter_by(league_id=league.id, season=2026, week=1).count() == 0
    assert db_session.query(TeamWeekScore).filter_by(league_id=league.id, season=2026, week=1).count() == 0


def test_empty_provider_result_refuses_to_overwrite_existing_scores(client, db_session):
    league, _home, _away, players, _matchup = create_scoring_fixture(db_session)
    recalculate_league_week_scores(db_session, league.id, 2026, 1)
    qb_score = db_session.query(PlayerWeekScore).filter_by(league_id=league.id, player_id=players["qb"].id, season=2026, week=1).one()
    assert qb_score.fantasy_points == 16.0

    db_session.query(PlayerStat).filter_by(season=2026, week=1).delete()

    with pytest.raises(ValueError, match="no provider stat rows"):
        recalculate_league_week_scores(db_session, league.id, 2026, 1)

    refreshed_qb_score = db_session.query(PlayerWeekScore).filter_by(league_id=league.id, player_id=players["qb"].id, season=2026, week=1).one()
    assert refreshed_qb_score.fantasy_points == 16.0


def test_partial_provider_result_marks_missing_starter_delayed(client, db_session):
    league, home, _away, players, matchup = create_scoring_fixture(db_session)
    db_session.query(PlayerStat).filter_by(player_id=players["qb"].id, season=2026, week=1).delete()

    summary = recalculate_league_week_scores(db_session, league.id, 2026, 1)
    db_session.commit()

    assert summary.players_scored == 5
    assert db_session.query(PlayerWeekScore).filter_by(league_id=league.id, player_id=players["qb"].id, season=2026, week=1).first() is None
    home_score = db_session.query(TeamWeekScore).filter_by(league_id=league.id, team_id=home.id, season=2026, week=1).one()
    assert home_score.status == "delayed"
    assert home_score.breakdown_json["missing_starter_scores"] == 1
    qb_breakdown = next(row for row in home_score.breakdown_json["players"] if row["player_id"] == players["qb"].id)
    assert qb_breakdown["status"] == "unavailable"
    db_session.refresh(matchup)
    assert matchup.status == "delayed"
