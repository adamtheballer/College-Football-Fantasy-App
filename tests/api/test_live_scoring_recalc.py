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

    assert first.players_scored == second.players_scored == 6
    assert db_session.query(LineupWeekSnapshot).filter_by(league_id=league.id, season=2026, week=1).count() == 6
    available_score = db_session.query(PlayerWeekScore).filter_by(league_id=league.id, player_id=players["available"].id, season=2026, week=1).one_or_none()
    assert available_score is None

    qb_score = db_session.query(PlayerWeekScore).filter_by(league_id=league.id, player_id=players["qb"].id, season=2026, week=1).one()
    assert qb_score.stat_version == 1
    assert qb_score.source_provider == "sportsdata"
    assert qb_score.previous_score is None
    assert qb_score.correction_delta == 0.0

    home_score = db_session.query(TeamWeekScore).filter_by(league_id=league.id, team_id=home.id, season=2026, week=1).one()
    assert home_score.starter_points == 56.0
    assert home_score.bench_points == 32.0
    assert home_score.total_points == 56.0
    assert any(row["player_id"] == players["bench"].id for row in home_score.breakdown_json["players"])


def test_recalculate_league_week_scores_skips_unrelated_players_without_stats(client, db_session):
    league, _home, _away, players, _matchup = create_scoring_fixture(db_session)

    summary = recalculate_league_week_scores(db_session, league.id, 2026, 1)
    db_session.commit()

    assert summary.players_scored == 6
    assert db_session.query(PlayerWeekScore).filter_by(league_id=league.id, season=2026, week=1).count() == 6
    assert (
        db_session.query(PlayerWeekScore)
        .filter_by(league_id=league.id, player_id=players["available"].id, season=2026, week=1)
        .one_or_none()
        is None
    )


def test_recalculate_league_week_scores_includes_free_agents_with_provider_stats(client, db_session):
    league, _home, _away, players, _matchup = create_scoring_fixture(db_session)
    db_session.add(
        PlayerStat(
            player_id=players["available"].id,
            season=2026,
            week=1,
            source="sportsdata",
            stats={"Receptions": 2, "ReceivingYards": 30},
        )
    )
    db_session.commit()

    summary = recalculate_league_week_scores(db_session, league.id, 2026, 1)
    db_session.commit()

    assert summary.players_scored == 7
    available_score = db_session.query(PlayerWeekScore).filter_by(league_id=league.id, player_id=players["available"].id, season=2026, week=1).one()
    assert available_score.fantasy_points == 5.0


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
    assert qb_score.stat_version == 2
    assert qb_score.previous_score == 16.0
    assert qb_score.correction_delta == 12.0
    assert home_score.total_points == 68.0

    recalculate_league_week_scores(db_session, league.id, 2026, 1)
    db_session.commit()
    db_session.refresh(qb_score)
    assert qb_score.stat_version == 2


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
