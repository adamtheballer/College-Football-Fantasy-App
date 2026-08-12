from datetime import datetime, timezone

import pytest

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.domain.live_scoring_contract import (
    IncompleteStatRevisionError,
    LiveScoringContractError,
    validate_lifecycle_transition,
)
from collegefootballfantasy_api.app.integrations.live_scoring_adapter import FrozenPayloadAdapter, ProviderPayloadError
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.live_scoring import (
    PlayerGameStatRevision,
    ProviderGameIdentity,
    ProviderRawEvent,
    ScoringCalculationSnapshot,
    ScoringCorrectionLedger,
    ScoringDeadLetter,
    ScoringWorkItem,
    ShadowScoringReadModel,
)
from collegefootballfantasy_api.app.models.provider_identity import PlayerProviderId
from collegefootballfantasy_api.app.services.live_scoring_service import (
    IdentityResolutionError,
    ImmutableProviderEventError,
    ProviderEventInput,
    calculate_snapshot,
    complete_work_item,
    enqueue_work,
    fail_work_item,
    lease_next_work_item,
    record_provider_event,
    record_stat_revision,
    process_one_scoring_work_item,
    replay_dead_letter,
)
from tests.api.scoring_helpers import create_scoring_fixture


def _identity_ready_fixture(db_session):
    league, _home, _away, players, _matchup = create_scoring_fixture(db_session)
    game = Game(season=2026, week=1, season_type="regular", home_team="Test", away_team="Opponent")
    db_session.add(game)
    db_session.flush()
    db_session.add_all(
        [
            PlayerProviderId(
                player_id=players["qb"].id,
                provider="trusted",
                provider_player_id="provider-qb-1",
                verification_status="verified",
            ),
            ProviderGameIdentity(
                provider="trusted",
                provider_game_id="provider-game-1",
                game_id=game.id,
                verification_status="verified",
            ),
        ]
    )
    db_session.commit()
    return league, players["qb"], game


def _event(db_session, *, event_id="event-1", payload=None):
    return record_provider_event(
        db_session,
        ProviderEventInput(
            provider="trusted",
            feed="live_box_score",
            provider_event_id=event_id,
            provider_player_id="provider-qb-1",
            provider_game_id="provider-game-1",
            season=2026,
            week=1,
            payload=payload or {"event": event_id, "stats": {"PassingYards": 250}},
        ),
    )


def test_raw_events_are_idempotent_and_never_overwritten(client, db_session):
    _identity_ready_fixture(db_session)
    first = _event(db_session)
    duplicate = _event(db_session)
    assert duplicate.id == first.id
    assert db_session.query(ProviderRawEvent).count() == 1

    with pytest.raises(ImmutableProviderEventError):
        _event(db_session, payload={"event": "event-1", "stats": {"PassingYards": 999}})
    assert db_session.query(ProviderRawEvent).count() == 1


def test_unverified_or_missing_identity_cannot_create_a_revision(client, db_session):
    _identity_ready_fixture(db_session)
    db_session.query(PlayerProviderId).update({"verification_status": "unverified"})
    event = _event(db_session)
    with pytest.raises(IdentityResolutionError):
        record_stat_revision(
            db_session, raw_event=event, position="QB", season=2026, week=1,
            lifecycle_state="live", completeness="complete", stats={"PassingYards": 250},
        )
    assert db_session.query(PlayerGameStatRevision).count() == 0


def test_missing_stat_is_never_silently_scored_as_zero(client, db_session):
    league, _player, _game = _identity_ready_fixture(db_session)
    event = _event(db_session)
    revision = record_stat_revision(
        db_session, raw_event=event, position="QB", season=2026, week=1,
        lifecycle_state="live", completeness="incomplete", stats={"PassingYards": 250},
    )
    assert revision.status == "blocked_incomplete"
    assert revision.stats_json["pass_tds"] is None
    with pytest.raises(IncompleteStatRevisionError):
        calculate_snapshot(db_session, league_id=league.id, revision=revision, scoring_rules={})
    assert db_session.query(ScoringCalculationSnapshot).count() == 0


def test_explicitly_complete_zeroes_are_scoreable_and_snapshots_are_idempotent(client, db_session, monkeypatch):
    league, _player, _game = _identity_ready_fixture(db_session)
    monkeypatch.setattr(settings, "scoring_mode", "shadow")
    event = _event(db_session)
    revision = record_stat_revision(
        db_session, raw_event=event, position="QB", season=2026, week=1,
        lifecycle_state="final", completeness="complete", stats={"PassingYards": 250, "PassingTouchdowns": 2},
    )
    first = calculate_snapshot(db_session, league_id=league.id, revision=revision, scoring_rules={})
    second = calculate_snapshot(db_session, league_id=league.id, revision=revision, scoring_rules={})
    assert first.id == second.id
    assert first.publish_state == "shadow"
    assert first.score == 18.0
    assert db_session.query(ScoringCalculationSnapshot).count() == 1


def test_stat_corrections_append_revisions_and_a_ledger_entry(client, db_session):
    _league, _player, _game = _identity_ready_fixture(db_session)
    first_event = _event(db_session, event_id="event-1")
    first = record_stat_revision(
        db_session, raw_event=first_event, position="QB", season=2026, week=1,
        lifecycle_state="final", completeness="complete", stats={"PassingYards": 250},
    )
    second_event = _event(db_session, event_id="event-2")
    second = record_stat_revision(
        db_session, raw_event=second_event, position="QB", season=2026, week=1,
        lifecycle_state="corrected", completeness="complete", stats={"PassingYards": 300},
        correction_reason="provider final correction",
    )
    assert first.revision_number == 1
    assert second.revision_number == 2
    assert second.supersedes_revision_id == first.id
    assert db_session.query(PlayerGameStatRevision).count() == 2
    ledger = db_session.query(ScoringCorrectionLedger).one()
    assert ledger.prior_revision_id == first.id
    assert ledger.corrected_revision_id == second.id


def test_queue_is_idempotent_leased_and_dead_letters_after_max_attempts(client, db_session):
    first = enqueue_work(db_session, task_type="score_revision", idempotency_key="revision:1", payload={"revision_id": 1}, max_attempts=2)
    duplicate = enqueue_work(db_session, task_type="score_revision", idempotency_key="revision:1", payload={"revision_id": 1})
    assert first.id == duplicate.id
    leased = lease_next_work_item(db_session, worker_id="worker-a")
    assert leased is not None and leased.status == "leased" and leased.attempts == 1
    fail_work_item(db_session, leased, worker_id="worker-a", category="network", message="temporary timeout")
    leased.next_attempt_at = datetime.now(timezone.utc)
    db_session.flush()
    retried = lease_next_work_item(db_session, worker_id="worker-b")
    assert retried is not None and retried.id == first.id
    fail_work_item(db_session, retried, worker_id="worker-b", category="network", message="second timeout")
    assert retried.status == "dead_letter"
    assert db_session.query(ScoringDeadLetter).count() == 1
    assert lease_next_work_item(db_session, worker_id="worker-c") is None
    replayed = replay_dead_letter(db_session, dead_letter_id=db_session.query(ScoringDeadLetter).one().id)
    assert replayed.status == "pending"
    assert replayed.attempts == 0
    assert db_session.query(ScoringDeadLetter).one().replayed_at is not None


def test_only_current_lease_holder_can_complete_work(client, db_session):
    enqueue_work(db_session, task_type="score_revision", idempotency_key="revision:2", payload={})
    item = lease_next_work_item(db_session, worker_id="worker-a")
    assert item is not None
    with pytest.raises(Exception, match="current lease holder"):
        complete_work_item(db_session, item, worker_id="worker-b")
    complete_work_item(db_session, item, worker_id="worker-a")
    assert item.status == "succeeded"


def test_queue_processor_creates_a_shadow_snapshot_without_provider_network(client, db_session, monkeypatch):
    league, _player, _game = _identity_ready_fixture(db_session)
    monkeypatch.setattr(settings, "scoring_mode", "shadow")
    event = _event(db_session)
    revision = record_stat_revision(
        db_session,
        raw_event=event,
        position="QB",
        season=2026,
        week=1,
        lifecycle_state="final",
        completeness="complete",
        stats={"PassingYards": 250},
    )
    enqueue_work(
        db_session,
        task_type="score_revision",
        idempotency_key=f"snapshot:{league.id}:{revision.id}",
        payload={"league_id": league.id, "revision_id": revision.id},
    )
    processed = process_one_scoring_work_item(db_session, worker_id="worker-a")
    assert processed is not None and processed.status == "succeeded"
    snapshot = db_session.query(ScoringCalculationSnapshot).one()
    assert snapshot.publish_state == "shadow"
    # The next durable task creates an immutable league read model.  It is
    # deliberately distinct from any public scoring table.
    projected = process_one_scoring_work_item(db_session, worker_id="worker-a")
    assert projected is not None and projected.status == "succeeded"
    assert db_session.query(ShadowScoringReadModel).count() == 1


def test_scoring_policy_snapshot_is_immutable_per_league_and_season(client, db_session, monkeypatch):
    league, _player, _game = _identity_ready_fixture(db_session)
    monkeypatch.setattr(settings, "scoring_mode", "shadow")
    event = _event(db_session)
    revision = record_stat_revision(
        db_session,
        raw_event=event,
        position="QB",
        season=2026,
        week=1,
        lifecycle_state="final",
        completeness="complete",
        stats={"PassingYards": 250},
    )
    standard = calculate_snapshot(db_session, league_id=league.id, revision=revision, scoring_rules={})
    altered = calculate_snapshot(
        db_session,
        league_id=league.id,
        revision=revision,
        scoring_rules={"pass_yd": 0.05},
    )
    assert standard.league_scoring_snapshot_id != altered.league_scoring_snapshot_id
    assert standard.scoring_policy_hash != altered.scoring_policy_hash
    assert db_session.query(ScoringCalculationSnapshot).count() == 2


def test_game_lifecycle_rejects_invalid_transition_and_allows_final_correction():
    with pytest.raises(LiveScoringContractError, match="invalid game lifecycle transition"):
        validate_lifecycle_transition("scheduled", "final")
    validate_lifecycle_transition("final", "corrected")


def test_frozen_adapter_is_pure_and_requires_exact_provider_ids():
    adapter = FrozenPayloadAdapter(provider="trusted")
    event = adapter.normalize_event(
        {
            "event_id": "event-1",
            "provider_player_id": "provider-qb-1",
            "provider_game_id": "provider-game-1",
            "season": 2026,
            "week": 1,
            "stats": {"PassingYards": 250},
        }
    )
    assert event.provider == "trusted"
    assert event.provider_player_id == "provider-qb-1"
    with pytest.raises(ProviderPayloadError):
        adapter.normalize_event({"event_id": "event-1", "stats": {}})
