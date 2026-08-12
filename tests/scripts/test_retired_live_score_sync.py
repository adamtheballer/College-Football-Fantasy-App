import argparse

import pytest

from scripts.sync_live_scores import run_once


def test_retired_direct_sync_cannot_fetch_provider_or_write_scores():
    with pytest.raises(RuntimeError, match="Direct live-score synchronization is retired"):
        run_once(argparse.Namespace(season=2026, week=1, league_id=None, provider="sportsdata", watch=False))
