from datetime import datetime, timezone

from scripts.sync_official_availability_reports import should_run_at_local_hour


def test_daily_availability_cron_runs_once_at_ten_am_new_york_across_dst():
    # 10 AM EDT, then the paired 11 AM EDT run that must no-op.
    assert should_run_at_local_hour(
        datetime(2026, 8, 20, 14, tzinfo=timezone.utc),
        timezone_name="America/New_York",
        hour=10,
    )
    assert not should_run_at_local_hour(
        datetime(2026, 8, 20, 15, tzinfo=timezone.utc),
        timezone_name="America/New_York",
        hour=10,
    )

    # 10 AM EST, then the paired 9 AM EST run that must no-op.
    assert should_run_at_local_hour(
        datetime(2026, 12, 20, 15, tzinfo=timezone.utc),
        timezone_name="America/New_York",
        hour=10,
    )
    assert not should_run_at_local_hour(
        datetime(2026, 12, 20, 14, tzinfo=timezone.utc),
        timezone_name="America/New_York",
        hour=10,
    )
