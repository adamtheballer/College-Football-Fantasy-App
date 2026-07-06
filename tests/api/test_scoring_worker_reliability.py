from datetime import datetime, timedelta, timezone

import pytest

from collegefootballfantasy_api.app.models.scoring_job_lock import ScoringJobLock
from collegefootballfantasy_api.app.models.scoring_run import ScoringRun
from collegefootballfantasy_api.app.services.scoring_worker_service import (
    ProviderSyncFailed,
    RetryPolicy,
    acquire_scoring_lock,
    recover_stale_scoring_runs,
    release_scoring_lock,
    run_scoring_worker_once,
)
from tests.api.scoring_helpers import create_scoring_fixture


def test_scoring_lock_prevents_duplicate_active_run(client, db_session):
    now = datetime.now(timezone.utc)
    first = acquire_scoring_lock(
        db_session,
        provider="espn",
        season=2026,
        week=1,
        league_id=1,
        worker_id="worker-a",
        ttl_seconds=300,
        now=now,
    )
    second = acquire_scoring_lock(
        db_session,
        provider="espn",
        season=2026,
        week=1,
        league_id=1,
        worker_id="worker-b",
        ttl_seconds=300,
        now=now,
    )

    assert first is not None
    assert second is None

    release_scoring_lock(db_session, first, now=now + timedelta(seconds=1))
    third = acquire_scoring_lock(
        db_session,
        provider="espn",
        season=2026,
        week=1,
        league_id=1,
        worker_id="worker-c",
        ttl_seconds=300,
        now=now + timedelta(seconds=2),
    )

    assert third is not None
    assert third.worker_id == "worker-c"


def test_expired_scoring_lock_can_be_recovered(client, db_session):
    now = datetime.now(timezone.utc)
    first = acquire_scoring_lock(
        db_session,
        provider="espn",
        season=2026,
        week=1,
        league_id=1,
        worker_id="stale-worker",
        ttl_seconds=10,
        now=now,
    )
    recovered = acquire_scoring_lock(
        db_session,
        provider="espn",
        season=2026,
        week=1,
        league_id=1,
        worker_id="new-worker",
        ttl_seconds=10,
        now=now + timedelta(seconds=11),
    )

    assert first is not None
    assert recovered is not None
    assert recovered.id == first.id
    assert recovered.worker_id == "new-worker"


def test_duplicate_worker_run_exits_without_scoring(client, db_session):
    league, *_ = create_scoring_fixture(db_session)
    acquire_scoring_lock(
        db_session,
        provider="espn",
        season=2026,
        week=1,
        league_id=league.id,
        worker_id="active-worker",
        ttl_seconds=300,
    )

    result = run_scoring_worker_once(
        db_session,
        provider="espn",
        season=2026,
        week=1,
        league_id=league.id,
        sync_provider_stats=lambda: {"rows_seen": 1, "upserted": 1, "skipped": 0, "events": 1},
        worker_id="duplicate-worker",
    )

    assert result.status == "skipped"
    assert result.lock_acquired is False
    assert db_session.query(ScoringRun).count() == 0


def test_temporary_provider_failure_retries_and_records_telemetry(client, db_session):
    league, *_ = create_scoring_fixture(db_session)
    attempts = {"count": 0}

    def sync_provider_stats():
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("temporary provider failure")
        return {"rows_seen": 3, "upserted": 2, "skipped": 1, "events": 4, "data_age_seconds": 12}

    result = run_scoring_worker_once(
        db_session,
        provider="espn",
        season=2026,
        week=1,
        league_id=league.id,
        sync_provider_stats=sync_provider_stats,
        retry_policy=RetryPolicy(max_attempts=2, initial_backoff_seconds=0),
        worker_id="retry-worker",
        sleeper=lambda _seconds: None,
    )

    run = db_session.query(ScoringRun).filter_by(id=result.run_id).one()
    lock = db_session.query(ScoringJobLock).filter_by(lock_key=run.lock_key).one()
    assert result.status == "success"
    assert attempts["count"] == 2
    assert run.retry_count == 1
    assert run.rows_fetched == 3
    assert run.rows_matched == 2
    assert run.rows_unmatched == 1
    assert run.provider_events_seen == 4
    assert run.data_age_seconds == 12
    assert run.players_updated == 7
    assert lock.status == "released"


def test_permanent_provider_failure_records_failed_run_and_releases_lock(client, db_session):
    league, *_ = create_scoring_fixture(db_session)

    with pytest.raises(ProviderSyncFailed):
        run_scoring_worker_once(
            db_session,
            provider="espn",
            season=2026,
            week=1,
            league_id=league.id,
            sync_provider_stats=lambda: (_ for _ in ()).throw(RuntimeError("provider down")),
            retry_policy=RetryPolicy(max_attempts=2, initial_backoff_seconds=0),
            worker_id="failed-worker",
            sleeper=lambda _seconds: None,
        )

    run = db_session.query(ScoringRun).filter_by(provider="espn", status="failed").one()
    lock = db_session.query(ScoringJobLock).filter_by(lock_key=run.lock_key).one()
    assert run.retry_count == 1
    assert run.error_message == "provider sync failed"
    assert lock.status == "released"


def test_stale_scoring_runs_are_marked_failed(client, db_session):
    old_started_at = datetime.now(timezone.utc) - timedelta(minutes=30)
    run = ScoringRun(
        league_id=1,
        season=2026,
        week=1,
        provider="espn",
        status="running",
        started_at=old_started_at,
    )
    db_session.add(run)
    db_session.commit()

    recovered = recover_stale_scoring_runs(
        db_session,
        older_than_seconds=900,
        now=datetime.now(timezone.utc),
    )
    db_session.commit()

    refreshed = db_session.get(ScoringRun, run.id)
    assert recovered == 1
    assert refreshed.status == "failed"
    assert refreshed.error_message == "stale scoring run recovered"
