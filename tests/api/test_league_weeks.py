from datetime import datetime, timezone

from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.services.league_weeks import calendar_cfb_week, resolve_current_week
from tests.api.scoring_helpers import create_scoring_fixture


def test_opening_saturday_is_part_of_week_one():
    assert calendar_cfb_week(2026, datetime(2026, 8, 29, 19, 0, tzinfo=timezone.utc)) == 1


def test_current_week_does_not_skip_the_calendar_active_matchup_when_scoring_is_delayed(db_session):
    league, home, away, _players, week_one = create_scoring_fixture(db_session)
    # Reproduce the production state at kickoff: Week 1 exists, but the
    # scoring worker has not yet promoted the fantasy matchup to "live".
    week_one.status = "unavailable"
    db_session.add(
        Matchup(
            league_id=league.id,
            season=2026,
            week=2,
            home_team_id=home.id,
            away_team_id=away.id,
            status="scheduled",
        )
    )
    db_session.commit()

    assert resolve_current_week(
        db_session,
        league,
        now=datetime(2026, 8, 29, 19, 0, tzinfo=timezone.utc),
    ) == 1


def test_current_week_keeps_using_status_priority_when_no_calendar_week_matchup_exists(db_session):
    league, home, away, _players, week_one = create_scoring_fixture(db_session)
    db_session.delete(week_one)
    db_session.add(
        Matchup(
            league_id=league.id,
            season=2026,
            week=3,
            home_team_id=home.id,
            away_team_id=away.id,
            status="live",
        )
    )
    db_session.commit()

    assert resolve_current_week(
        db_session,
        league,
        now=datetime(2026, 8, 29, 19, 0, tzinfo=timezone.utc),
    ) == 3
