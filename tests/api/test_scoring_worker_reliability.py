from datetime import datetime, timedelta, timezone

import pytest

from conftest import TestingSessionLocal
from collegefootballfantasy_api.app.models.scoring_job_lock import ScoringJobLock
from collegefootballfantasy_api.app.models.scoring_run import ScoringRun
from collegefootballfantasy_api.app.services import scoring_worker_service
from collegefootballfantasy_api.app.services.scoring_worker_service import (
    ProviderDataValidationFailed,
    ProviderSyncFailed,
    RetryPolicy,
    acquire_scoring_lock,
    recover_stale_scoring_runs,
    release_scoring_lock,
    run_scoring_worker_once,
)
from collegefootballfantasy_api.app.services.scoring_service import run_league_scoring_recalculation
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


def test_all_league_lock_blocks_specific_league_lock(client, db_session):
    league, *_ = create_scoring_fixture(db_session)
    all_lock = acquire_scoring_lock(
        db_session,
        provider="espn",
        season=2026,
        week=1,
        league_id=None,
        worker_id="all-worker",
        ttl_seconds=300,
    )
    specific_lock = acquire_scoring_lock(
        db_session,
        provider="espn",
        season=2026,
        week=1,
        league_id=league.id,
        worker_id="specific-worker",
        ttl_seconds=300,
    )

    assert all_lock is not None
    assert specific_lock is None


def test_specific_league_lock_blocks_all_league_lock(client, db_session):
    league, *_ = create_scoring_fixture(db_session)
    specific_lock = acquire_scoring_lock(
        db_session,
        provider="espn",
        season=2026,
        week=1,
        league_id=league.id,
        worker_id="specific-worker",
        ttl_seconds=300,
    )
    all_lock = acquire_scoring_lock(
        db_session,
        provider="espn",
        season=2026,
        week=1,
        league_id=None,
        worker_id="all-worker",
        ttl_seconds=300,
    )

    assert specific_lock is not None
    assert all_lock is None


def test_committed_lock_is_visible_to_second_worker_session(client, db_session):
    league, *_ = create_scoring_fixture(db_session)

    with TestingSessionLocal() as session_a:
        lock = acquire_scoring_lock(
            session_a,
            provider="espn",
            season=2026,
            week=1,
            league_id=league.id,
            worker_id="visible-worker",
            ttl_seconds=300,
        )
        assert lock is not None
        session_a.commit()

    with TestingSessionLocal() as session_b:
        active_lock = session_b.query(ScoringJobLock).filter_by(league_id=league.id, status="active").one()
        result = run_scoring_worker_once(
            session_b,
            provider="espn",
            season=2026,
            week=1,
            league_id=league.id,
            sync_provider_stats=lambda: {"rows_seen": 1, "upserted": 1, "skipped": 0, "events": 1},
            worker_id="blocked-worker",
        )

        assert active_lock.worker_id == "visible-worker"
        assert result.status == "skipped"
        assert result.lock_acquired is False


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


def test_empty_provider_success_does_not_recalculate_existing_scores(client, db_session):
    league, _home, _away, _players, matchup = create_scoring_fixture(db_session)
    result = run_scoring_worker_once(
        db_session,
        provider="espn",
        season=2026,
        week=1,
        league_id=league.id,
        sync_provider_stats=lambda: {"rows_seen": 1, "upserted": 1, "skipped": 0, "events": 1},
        worker_id="initial-worker",
    )
    assert result.status == "success"
    original_matchup = db_session.get(type(matchup), matchup.id)
    original_home_score = original_matchup.home_score

    with pytest.raises(ProviderDataValidationFailed):
        run_scoring_worker_once(
            db_session,
            provider="espn",
            season=2026,
            week=1,
            league_id=league.id,
            sync_provider_stats=lambda: {"rows_seen": 0, "upserted": 0, "skipped": 0, "events": 0},
            worker_id="empty-provider-worker",
        )

    failed_run = db_session.query(ScoringRun).filter_by(worker_id="empty-provider-worker").one()
    refreshed_matchup = db_session.get(type(matchup), matchup.id)
    assert failed_run.status == "failed"
    assert "zero stat rows" in failed_run.error_message
    assert refreshed_matchup.home_score == original_home_score


def test_provider_events_without_player_rows_do_not_recalculate_scores(client, db_session):
    league, _home, _away, _players, matchup = create_scoring_fixture(db_session)
    result = run_scoring_worker_once(
        db_session,
        provider="espn",
        season=2026,
        week=1,
        league_id=league.id,
        sync_provider_stats=lambda: {"rows_seen": 1, "upserted": 1, "skipped": 0, "events": 1},
        worker_id="initial-worker",
    )
    assert result.status == "success"
    original_home_score = db_session.get(type(matchup), matchup.id).home_score

    with pytest.raises(ProviderDataValidationFailed):
        run_scoring_worker_once(
            db_session,
            provider="espn",
            season=2026,
            week=1,
            league_id=league.id,
            sync_provider_stats=lambda: {"rows_seen": 0, "upserted": 0, "skipped": 0, "events": 3},
            worker_id="events-only-worker",
        )

    failed_run = db_session.query(ScoringRun).filter_by(worker_id="events-only-worker").one()
    assert failed_run.status == "failed"
    assert db_session.get(type(matchup), matchup.id).home_score == original_home_score


def test_worker_heartbeats_before_and_after_each_league_recalculation(client, db_session, monkeypatch):
    create_scoring_fixture(db_session)
    create_scoring_fixture(db_session)
    heartbeat_calls = []
    original_heartbeat = scoring_worker_service.heartbeat_scoring_lock

    def spy_heartbeat(*args, **kwargs):
        heartbeat_calls.append(kwargs.get("now"))
        return original_heartbeat(*args, **kwargs)

    monkeypatch.setattr(scoring_worker_service, "heartbeat_scoring_lock", spy_heartbeat)

    result = run_scoring_worker_once(
        db_session,
        provider="espn",
        season=2026,
        week=1,
        league_id=None,
        sync_provider_stats=lambda: {"rows_seen": 1, "upserted": 1, "skipped": 0, "events": 1},
        worker_id="heartbeat-worker",
    )

    assert result.status == "success"
    assert len(heartbeat_calls) == 4


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


def test_manual_recalculation_respects_active_worker_lock(client, db_session):
    league, *_ = create_scoring_fixture(db_session)
    lock = acquire_scoring_lock(
        db_session,
        provider="espn",
        season=2026,
        week=1,
        league_id=league.id,
        worker_id="live-worker",
        ttl_seconds=300,
    )
    assert lock is not None
    db_session.commit()

    with pytest.raises(ValueError, match="scoring job already running"):
        run_league_scoring_recalculation(db_session, league.id, 2026, 1)


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
