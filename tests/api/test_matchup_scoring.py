from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.matchup_score_version import MatchupScoreVersion
from collegefootballfantasy_api.app.services.matchup_finalization import mark_league_week_pending_final
from collegefootballfantasy_api.app.services.scoring_service import finalize_league_week_scores, recalculate_league_week_scores
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
    version = db_session.query(MatchupScoreVersion).filter_by(matchup_id=matchup.id).one()
    assert version.version == 1
    assert version.home_score == 56.0
    assert version.reason == "live_score_update"


def test_final_matchup_status_is_preserved_during_score_refresh(client, db_session):
    league, _home, _away, _players, matchup = create_scoring_fixture(db_session)
    matchup.status = "final"
    matchup.home_score = 10.0
    matchup.away_score = 9.0

    recalculate_league_week_scores(db_session, league.id, 2026, 1)
    db_session.commit()

    row = db_session.get(Matchup, matchup.id)
    assert row.status == "final"
    assert row.home_score == 10.0
    assert row.away_score == 9.0


def test_pending_final_and_final_versions_are_recorded(client, db_session):
    league, _home, _away, _players, matchup = create_scoring_fixture(db_session)
    recalculate_league_week_scores(db_session, league.id, 2026, 1)
    mark_league_week_pending_final(db_session, league.id, 2026, 1)
    db_session.commit()

    row = db_session.get(Matchup, matchup.id)
    assert row.status == "pending_final"

    finalize_league_week_scores(db_session, league.id, 2026, 1)
    db_session.commit()

    versions = db_session.query(MatchupScoreVersion).filter_by(matchup_id=matchup.id).order_by(MatchupScoreVersion.version.asc()).all()
    assert [version.reason for version in versions] == [
        "live_score_update",
        "provider_games_final",
        "all_starters_final",
    ]
    assert versions[-1].home_score == 56.0
