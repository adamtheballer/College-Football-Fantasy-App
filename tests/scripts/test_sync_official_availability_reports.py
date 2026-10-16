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


def test_conference_refresh_commits_healthy_sources_and_records_partial_failure(db_session, monkeypatch):
    from scripts import sync_official_availability_reports as job
    from conftest import TestingSessionLocal
    from collegefootballfantasy_api.app.models.player import Player
    from collegefootballfantasy_api.app.models.provider_sync_state import ProviderSyncState
    monkeypatch.setattr(job, 'SessionLocal', TestingSessionLocal)
    def sync(session, *, season, week, conference):
        session.add(Player(name=f'Isolated source {conference}', school='Texas', position='QB'))
        session.flush()
        if conference == 'ACC':
            raise RuntimeError('Unreadable official ACC report')
        return {'created':1,'updated':0,'rows_seen':1,'source':'official_conference_reports'}
    monkeypatch.setattr(job, 'sync_power4_injuries', sync)
    results = job.refresh_conferences(season=2026, week=7)
    assert results['SEC']['created'] == 1 and results['BIG12']['created'] == 1 and results['BIG10']['created'] == 1
    assert 'Unreadable' in results['ACC']['error']
    assert db_session.query(Player).count() == 3
    states = db_session.query(ProviderSyncState).all()
    assert len(states) == 4
    assert sorted(s.status for s in states) == ['failed','ready','ready','ready']
    failed = next(s for s in states if s.status == 'failed')
    assert failed.last_success_at is None and failed.consecutive_failures == 1


def test_deployed_schedule_refreshes_throughout_the_week():
    from pathlib import Path
    import tomllib
    root = Path(__file__).resolve().parents[2]
    config = tomllib.loads((root/'railway.availability-scheduler.toml').read_text())['deploy']
    assert config['cronSchedule'] == '*/30 * * * *'
    assert '--only-local-weekday' not in config['startCommand']
    assert '--only-local-hour' not in config['startCommand']
