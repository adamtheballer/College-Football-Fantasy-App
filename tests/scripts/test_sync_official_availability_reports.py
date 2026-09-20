from datetime import datetime, timezone

from scripts.sync_official_availability_reports import should_run_at_local_hour, should_run_at_local_schedule


def test_availability_cron_runs_once_at_ten_am_new_york_across_dst():
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


def test_availability_cron_supports_multiple_local_hours_without_dst_duplicates():
    # 5 PM EDT and 5 PM EST respectively. The paired UTC schedule for the
    # other daylight-saving offset must continue to no-op.
    assert should_run_at_local_hour(
        datetime(2026, 8, 20, 21, tzinfo=timezone.utc),
        timezone_name="America/New_York",
        hour=[10, 17],
    )
    assert not should_run_at_local_hour(
        datetime(2026, 8, 20, 22, tzinfo=timezone.utc),
        timezone_name="America/New_York",
        hour=[10, 17],
    )
    assert should_run_at_local_hour(
        datetime(2026, 12, 20, 22, tzinfo=timezone.utc),
        timezone_name="America/New_York",
        hour=[10, 17],
    )
    assert not should_run_at_local_hour(
        datetime(2026, 12, 20, 21, tzinfo=timezone.utc),
        timezone_name="America/New_York",
        hour=[10, 17],
    )


def test_availability_schedule_is_limited_to_wednesday_and_sunday_mornings():
    # Wednesday 10 AM EDT and Sunday 10 AM EST are accepted.
    assert should_run_at_local_schedule(
        datetime(2026, 9, 23, 14, tzinfo=timezone.utc),
        timezone_name="America/New_York",
        hour=10,
        weekday=[2, 6],
    )
    assert should_run_at_local_schedule(
        datetime(2026, 12, 20, 15, tzinfo=timezone.utc),
        timezone_name="America/New_York",
        hour=10,
        weekday=[2, 6],
    )
    # The alternate UTC hour and all off-days must no-op.
    assert not should_run_at_local_schedule(
        datetime(2026, 9, 23, 15, tzinfo=timezone.utc),
        timezone_name="America/New_York",
        hour=10,
        weekday=[2, 6],
    )
    assert not should_run_at_local_schedule(
        datetime(2026, 9, 22, 14, tzinfo=timezone.utc),
        timezone_name="America/New_York",
        hour=10,
        weekday=[2, 6],
    )
