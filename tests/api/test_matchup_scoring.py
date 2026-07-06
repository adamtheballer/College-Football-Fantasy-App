from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.services.scoring_service import recalculate_league_week_scores
from tests.api.scoring_helpers import create_scoring_fixture


def test_matchup_score_updates_from_team_scores(client, db_session):
    league, home, away, _players, matchup = create_scoring_fixture(db_session)

    summary = recalculate_league_week_scores(db_session, league.id, 2026, 1)
    db_session.commit()

    row = db_session.get(Matchup, matchup.id)
    assert summary.matchups_updated == 1
    assert row.home_score == 56.0
    assert row.away_score == 4.0
    assert row.status == "live"


def test_final_matchup_status_is_preserved_during_score_refresh(client, db_session):
    league, _home, _away, _players, matchup = create_scoring_fixture(db_session)
    matchup.status = "final"

    recalculate_league_week_scores(db_session, league.id, 2026, 1)
    db_session.commit()

    row = db_session.get(Matchup, matchup.id)
    assert row.status == "final"
