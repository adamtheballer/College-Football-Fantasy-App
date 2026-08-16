from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest

from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from scripts import run_espn_scoring_worker as worker
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


def test_worker_registers_orm_models_before_its_first_schedule_query(monkeypatch):
    registered = []

    class FakeSession:
        def commit(self):
            return None

    @contextmanager
    def fake_session():
        yield FakeSession()

    monkeypatch.setattr(worker.settings, "scoring_mode", "shadow")
    monkeypatch.setattr(worker.settings, "scoring_provider", "espn")
    monkeypatch.setattr(worker, "ensure_models_registered", lambda: registered.append(True))
    monkeypatch.setattr(worker, "SessionLocal", fake_session)
    monkeypatch.setattr(worker, "resolve_scoring_window", lambda _db, now=None: None)
    monkeypatch.setattr(worker, "record_worker_heartbeat", lambda *_args, **_kwargs: None)

    assert worker.run_iteration(now=NOW) is None
    assert registered == [True]


def test_once_mode_returns_a_nonzero_failure_instead_of_hiding_worker_boot_errors(monkeypatch):
    monkeypatch.setattr(worker.settings, "scoring_mode", "shadow")
    monkeypatch.setattr(worker.settings, "scoring_provider", "espn")
    monkeypatch.setattr(worker, "parse_args", lambda: worker.argparse.Namespace(once=True, interval_seconds=30))
    monkeypatch.setattr(worker, "run_iteration", lambda: (_ for _ in ()).throw(RuntimeError("mapper failed")))

    with pytest.raises(RuntimeError, match="mapper failed"):
        worker.main()
