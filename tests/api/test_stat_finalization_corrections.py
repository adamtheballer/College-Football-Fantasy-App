from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.scoring_correction_audit import ScoringCorrectionAudit
from collegefootballfantasy_api.app.models.standing import Standing
from collegefootballfantasy_api.app.models.team_week_score import TeamWeekScore
from collegefootballfantasy_api.app.services.scoring_service import (
    apply_stat_correction,
    finalize_league_week_scores,
    recalculate_league_week_scores,
)
from tests.api.scoring_helpers import create_scoring_fixture


def test_live_recalculation_does_not_update_standings_until_final(client, db_session):
    league, home, away, _players, matchup = create_scoring_fixture(db_session)

    recalculate_league_week_scores(db_session, league.id, 2026, 1)
    db_session.commit()

    assert db_session.get(Matchup, matchup.id).status == "live"
    home_standing = db_session.query(Standing).filter_by(league_id=league.id, team_id=home.id, season=2026, week=1).one()
    away_standing = db_session.query(Standing).filter_by(league_id=league.id, team_id=away.id, season=2026, week=1).one()
    assert (home_standing.wins, home_standing.losses, home_standing.points_for) == (0, 0, 0.0)
    assert (away_standing.wins, away_standing.losses, away_standing.points_for) == (0, 0, 0.0)


def test_finalize_league_week_scores_marks_matchups_final_and_updates_standings(client, db_session):
    league, home, away, _players, matchup = create_scoring_fixture(db_session)

    summary = finalize_league_week_scores(db_session, league.id, 2026, 1)
    db_session.commit()

    refreshed_matchup = db_session.get(Matchup, matchup.id)
    assert summary.matchups_updated == 1
    assert refreshed_matchup.status == "final"
    assert refreshed_matchup.home_score == 56.0
    home_team_score = db_session.query(TeamWeekScore).filter_by(league_id=league.id, team_id=home.id).one()
    assert home_team_score.status == "final"
    home_standing = db_session.query(Standing).filter_by(league_id=league.id, team_id=home.id, season=2026, week=1).one()
    away_standing = db_session.query(Standing).filter_by(league_id=league.id, team_id=away.id, season=2026, week=1).one()
    assert (home_standing.wins, home_standing.losses, home_standing.points_for) == (1, 0, 56.0)
    assert (away_standing.wins, away_standing.losses, away_standing.points_against) == (0, 1, 56.0)


def test_stat_correction_recalculates_scores_standings_and_records_audit(client, db_session):
    league, home, _away, players, matchup = create_scoring_fixture(db_session)
    finalize_league_week_scores(db_session, league.id, 2026, 1)
    db_session.commit()

    audit = apply_stat_correction(
        db_session,
        league_id=league.id,
        season=2026,
        week=1,
        player_id=players["qb"].id,
        corrected_stats={"PassingYards": 300, "PassingTouchdowns": 3, "Interceptions": 1},
        reason="Official stat correction",
        created_by_user_id=None,
    )
    db_session.commit()

    refreshed_matchup = db_session.get(Matchup, matchup.id)
    assert refreshed_matchup.status == "stat_corrected"
    assert refreshed_matchup.home_score == 62.0
    assert audit.old_fantasy_points == 16.0
    assert audit.new_fantasy_points == 22.0
    assert audit.old_matchup_statuses[str(matchup.id)] == "final"
    assert audit.new_matchup_statuses[str(matchup.id)] == "stat_corrected"
    saved_audit = db_session.query(ScoringCorrectionAudit).one()
    assert saved_audit.reason == "Official stat correction"
    home_standing = db_session.query(Standing).filter_by(league_id=league.id, team_id=home.id, season=2026, week=1).one()
    assert home_standing.points_for == 62.0
