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


def test_resolve_scoring_window_chooses_week_one_before_its_first_kickoff(db_session):
    """The next week must be the nearest slate, not the far edge of the horizon."""
    db_session.add_all(
        [
            TeamSchedule(
                team_name="Texas",
                season=2026,
                week=1,
                location="home",
                is_bye=False,
                kickoff_at=NOW + timedelta(days=1),
            ),
            TeamSchedule(
                team_name="Oregon",
                season=2026,
                week=2,
                location="away",
                is_bye=False,
                kickoff_at=NOW + timedelta(days=7),
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


def test_worker_records_liveness_before_enabled_scoring_preflight(monkeypatch):
    heartbeats = []

    class FakeSession:
        def commit(self):
            return None

    @contextmanager
    def fake_session():
        yield FakeSession()

    class FakeResult:
        discovered_games = 1
        claimed_games = 1
        successful_games = 1
        failed_games = 0
        unmatched_rows = 0

    def capture_heartbeat(*_args, **kwargs):
        heartbeats.append(kwargs)

    def run_cycle(*_args, **_kwargs):
        assert heartbeats == [
            {
                "worker_name": "espn_scoring_processor",
                "success": True,
                "details": {"state": "running", "season": 2026, "week": 1},
            }
        ]
        return FakeResult()

    monkeypatch.setattr(worker.settings, "scoring_mode", "enabled")
    monkeypatch.setattr(worker.settings, "scoring_provider", "espn")
    monkeypatch.setattr(worker, "ensure_models_registered", lambda: None)
    monkeypatch.setattr(worker, "SessionLocal", fake_session)
    monkeypatch.setattr(worker, "resolve_scoring_window", lambda _db, now=None: (2026, 1))
    monkeypatch.setattr(worker, "record_worker_heartbeat", capture_heartbeat)
    monkeypatch.setattr(worker, "run_espn_scoring_cycle", run_cycle)
    monkeypatch.setattr(worker, "scoring_operations_report", lambda *_args, **_kwargs: {"alerts": []})

    assert worker.run_iteration(now=NOW, client=object()) is not None
    assert heartbeats[-1]["success"] is True
    assert heartbeats[-1]["details"]["state"] == "completed"


def test_worker_records_a_failure_heartbeat_when_a_cycle_raises(monkeypatch):
    heartbeats = []

    class FakeSession:
        def commit(self):
            return None

    @contextmanager
    def fake_session():
        yield FakeSession()

    monkeypatch.setattr(worker.settings, "scoring_mode", "enabled")
    monkeypatch.setattr(worker.settings, "scoring_provider", "espn")
    monkeypatch.setattr(worker, "ensure_models_registered", lambda: None)
    monkeypatch.setattr(worker, "SessionLocal", fake_session)
    monkeypatch.setattr(worker, "resolve_scoring_window", lambda _db, now=None: (2026, 1))
    monkeypatch.setattr(worker, "record_worker_heartbeat", lambda *_args, **kwargs: heartbeats.append(kwargs))
    monkeypatch.setattr(worker, "run_espn_scoring_cycle", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("provider unavailable")))

    with pytest.raises(RuntimeError, match="provider unavailable"):
        worker.run_iteration(now=NOW, client=object())

    assert [item["success"] for item in heartbeats] == [True, False]
    assert heartbeats[-1]["details"]["state"] == "failed"


def test_once_mode_returns_a_nonzero_failure_instead_of_hiding_worker_boot_errors(monkeypatch):
    monkeypatch.setattr(worker.settings, "scoring_mode", "shadow")
    monkeypatch.setattr(worker.settings, "scoring_provider", "espn")
    monkeypatch.setattr(worker, "parse_args", lambda: worker.argparse.Namespace(once=True, interval_seconds=30))
    monkeypatch.setattr(worker, "run_iteration", lambda: (_ for _ in ()).throw(RuntimeError("mapper failed")))

    with pytest.raises(RuntimeError, match="mapper failed"):
        worker.main()


def test_worker_exits_for_supervisor_restart_after_repeated_fatal_iterations(monkeypatch):
    attempts = []

    monkeypatch.setattr(worker.settings, "scoring_mode", "shadow")
    monkeypatch.setattr(worker.settings, "scoring_provider", "espn")
    monkeypatch.setattr(worker, "parse_args", lambda: worker.argparse.Namespace(once=False, interval_seconds=30))
    monkeypatch.setattr(worker, "MAX_CONSECUTIVE_FATAL_ITERATIONS", 3)
    monkeypatch.setattr(worker.time, "sleep", lambda _seconds: None)

    def fail_iteration():
        attempts.append(True)
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(worker, "run_iteration", fail_iteration)

    with pytest.raises(RuntimeError, match="database unavailable"):
        worker.main()

    assert len(attempts) == 3
