import argparse

import pytest

from collegefootballfantasy_api.app.core.config import settings
from scripts.run_scoring_worker import run_iteration, schedule_for_mode


def test_scoring_worker_uses_distinct_cadence_profiles():
    live = schedule_for_mode("live")
    postgame = schedule_for_mode("postgame")
    correction = schedule_for_mode("correction")

    assert live.mode == "live"
    assert postgame.mode == "postgame"
    assert correction.mode == "correction"
    assert live.interval_seconds == 180
    assert live.interval_seconds < postgame.interval_seconds <= correction.interval_seconds


def test_scoring_worker_refuses_to_execute_when_scoring_is_disabled(monkeypatch):
    monkeypatch.setattr(settings, "scoring_mode", "disabled")

    with pytest.raises(RuntimeError, match="SCORING_MODE=disabled"):
        run_iteration(argparse.Namespace(season=2026, week=1, league_id=None, provider="sportsdata", mode="live"))


def test_legacy_manual_worker_refuses_espn_to_prevent_bypassing_the_durable_scheduler(monkeypatch):
    monkeypatch.setattr(settings, "scoring_mode", "shadow")
    with pytest.raises(RuntimeError, match="run_espn_scoring_worker.py"):
        run_iteration(argparse.Namespace(season=2026, week=1, league_id=None, provider="espn", mode="live"))
