from datetime import datetime, timezone

from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.services.league_weeks import calendar_cfb_week, resolve_current_week
from tests.api.scoring_helpers import create_scoring_fixture


def test_opening_saturday_is_part_of_week_one():
    assert calendar_cfb_week(2026, datetime(2026, 8, 29, 19, 0, tzinfo=timezone.utc)) == 1


def test_opening_week_remains_week_one_through_the_following_monday():
    assert calendar_cfb_week(2026, datetime(2026, 9, 1, 16, 0, tzinfo=timezone.utc)) == 1
    assert calendar_cfb_week(2026, datetime(2026, 9, 7, 23, 59, tzinfo=timezone.utc)) == 1
    assert calendar_cfb_week(2026, datetime(2026, 9, 8, 2, 46, tzinfo=timezone.utc)) == 1
    assert calendar_cfb_week(2026, datetime(2026, 9, 8, 3, 59, tzinfo=timezone.utc)) == 1
    assert calendar_cfb_week(2026, datetime(2026, 9, 8, 4, 0, tzinfo=timezone.utc)) == 2


def test_completed_matchup_stays_selected_until_eastern_reset(db_session, monkeypatch):
    from collegefootballfantasy_api.app.services import league_weeks
    from collegefootballfantasy_api.app.services.league_workspace import resolve_default_matchup_week

    league, home, away, _players, matchup = create_scoring_fixture(db_session)
    matchup.status = "final"
    db_session.add(Matchup(league_id=league.id, season=2026, week=2,
        home_team_id=home.id, away_team_id=away.id, status="scheduled"))
    db_session.commit()

    class Clock(datetime):
        current = datetime(2026, 9, 8, 2, 46, tzinfo=timezone.utc)

        @classmethod
        def now(cls, tz=None):
            return cls.current

    monkeypatch.setattr(league_weeks, "datetime", Clock)
    assert resolve_current_week(db_session, league) == 1
    assert resolve_default_matchup_week(db_session, league) == 1
    Clock.current = datetime(2026, 9, 8, 4, 0, tzinfo=timezone.utc)
    assert resolve_current_week(db_session, league) == 2
    assert resolve_default_matchup_week(db_session, league) == 2


def test_records_and_standings_publish_at_the_same_reset(db_session, monkeypatch):
    from collegefootballfantasy_api.app.services import league_weeks
    from collegefootballfantasy_api.app.services.league_workspace import build_standings_summary
    from collegefootballfantasy_api.app.services.league_roster_matchup import _team_records
    from collegefootballfantasy_api.app.models.standing import Standing

    league, home, away, _players, matchup = create_scoring_fixture(db_session)
    matchup.status = "final"
    matchup.home_score, matchup.away_score = 120, 100
    db_session.add(Standing(league_id=league.id, team_id=home.id, season=2026, week=1, wins=1, losses=0, ties=0))
    db_session.commit()

    class Clock(datetime):
        current = datetime(2026, 9, 8, 2, 46, tzinfo=timezone.utc)

        @classmethod
        def now(cls, tz=None):
            return cls.current

    monkeypatch.setattr(league_weeks, "datetime", Clock)
    assert _team_records(db_session, league, {home.id})[home.id] == "0-0-0"
    assert all(row.wins == 0 for row in build_standings_summary(db_session, league))
    Clock.current = datetime(2026, 9, 8, 4, tzinfo=timezone.utc)
    assert _team_records(db_session, league, {home.id})[home.id] == "1-0-0"
    assert next(row for row in build_standings_summary(db_session, league) if row.team_id == home.id).wins == 1


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
        now=datetime(2026, 9, 1, 16, 0, tzinfo=timezone.utc),
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
