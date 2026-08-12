import argparse
import sys

import pytest

from collegefootballfantasy_api.app.core.config import settings
from scripts.run_scoring_worker import run_iteration, schedule_for_mode
from scripts import compute_weekly_scores


def test_scoring_worker_uses_distinct_cadence_profiles():
    live = schedule_for_mode("live")
    postgame = schedule_for_mode("postgame")
    correction = schedule_for_mode("correction")

    assert live.mode == "live"
    assert postgame.mode == "postgame"
    assert correction.mode == "correction"
    assert live.interval_seconds < postgame.interval_seconds <= correction.interval_seconds


def test_scoring_worker_refuses_to_execute_when_scoring_is_disabled(monkeypatch):
    monkeypatch.setattr(settings, "scoring_mode", "disabled")

    with pytest.raises(RuntimeError, match="SCORING_MODE=disabled"):
        run_iteration(argparse.Namespace(season=2026, week=1, league_id=None, provider="sportsdata", mode="live"))


def test_scoring_worker_allows_shadow_mode_without_provider_polling(monkeypatch):
    monkeypatch.setattr(settings, "scoring_mode", "shadow")
    monkeypatch.setattr("scripts.run_scoring_worker.SessionLocal", lambda: _NoopSession())
    monkeypatch.setattr("scripts.run_scoring_worker.process_one_scoring_work_item", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("scripts.run_scoring_worker.record_worker_heartbeat", lambda *_args, **_kwargs: None)

    run_iteration(argparse.Namespace(season=2026, week=1, league_id=None, provider="sportsdata", mode="live"))


def test_legacy_weekly_score_script_refuses_mutable_writes_when_scoring_is_disabled(monkeypatch):
    monkeypatch.setattr(settings, "scoring_mode", "disabled")
    monkeypatch.setattr(sys, "argv", ["compute_weekly_scores.py", "--week", "1"])

    with pytest.raises(SystemExit, match="Refusing legacy mutable score writes"):
        compute_weekly_scores.main()


class _NoopSession:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def commit(self):
        return None
