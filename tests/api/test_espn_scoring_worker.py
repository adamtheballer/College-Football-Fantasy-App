from datetime import datetime, timedelta, timezone

from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from scripts.run_espn_scoring_worker import resolve_scoring_window


NOW = datetime(2026, 8, 29, 17, 0, tzinfo=timezone.utc)


def test_resolve_scoring_window_prefers_the_most_recent_verified_kickoff(db_session):
    db_session.add_all(
        [
            TeamSchedule(
                team_name="Texas",
                season=2026,
                week=1,
                location="home",
                is_bye=False,
                kickoff_at=NOW - timedelta(hours=3),
            ),
            TeamSchedule(
                team_name="Oregon",
                season=2026,
                week=2,
                location="away",
                is_bye=False,
                kickoff_at=NOW + timedelta(days=4),
            ),
        ]
    )
    db_session.commit()

    assert resolve_scoring_window(db_session, now=NOW) == (2026, 1)


def test_resolve_scoring_window_does_not_guess_when_only_byes_or_unverified_dates_exist(db_session):
    db_session.add_all(
        [
            TeamSchedule(team_name="Texas", season=2026, week=1, location="bye", is_bye=True),
            TeamSchedule(team_name="Oregon", season=2026, week=1, location="home", is_bye=False),
        ]
    )
    db_session.commit()

    assert resolve_scoring_window(db_session, now=NOW) is None
