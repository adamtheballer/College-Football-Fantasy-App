import sys

import pytest

from scripts.sync_live_scores import parse_args


def test_live_score_watch_defaults_to_the_approved_three_minute_cadence(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["sync_live_scores.py", "--season", "2025", "--week", "9"])

    args = parse_args()

    assert args.interval_seconds == 180


def test_live_score_watch_rejects_a_faster_provider_cadence(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["sync_live_scores.py", "--season", "2025", "--week", "9", "--interval-seconds", "179"],
    )

    with pytest.raises(SystemExit, match="--interval-seconds must be at least 180"):
        parse_args()
