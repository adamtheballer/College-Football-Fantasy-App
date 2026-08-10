from contextlib import nullcontext
from pathlib import Path

import pytest
from sqlalchemy import event

from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.services.cfb27_player_sync import Cfb27Rating
from scripts import bootstrap_canonical_player_data, reconcile_preseason_player_data


TEST_SOURCE_BATCH = "approved-test-batch"


def _approved_wayne_source_contract():
    return {
        "wayne_knight_projection_integrity": {
            "status": "PASS",
            "projection": {
                "name": "Wayne Knight",
                "team": "UCLA",
                "position": "RB",
                "fantasy_points": 265.0,
                "rush_yards": 1300.0,
                "rush_tds": 12.0,
                "receptions": 28.0,
                "rec_yards": 230.0,
                "rec_tds": 2.0,
            },
        },
        "gate_context": {"source_provenance": {"export_batch_id": TEST_SOURCE_BATCH}},
    }


def test_atomic_reconciler_rolls_back_catalog_when_rating_phase_fails(db_session, monkeypatch, tmp_path):
    monkeypatch.setattr(reconcile_preseason_player_data, "SessionLocal", lambda: nullcontext(db_session))
    monkeypatch.setattr(
        reconcile_preseason_player_data,
        "require_valid_source_directory",
        lambda _path: _approved_wayne_source_contract(),
    )
    monkeypatch.setattr(reconcile_preseason_player_data, "load_reviewed_cfb27_snapshot", lambda **_kwargs: object())

    def bootstrap_catalog(**kwargs):
        db = kwargs["db"]
        db.add(Player(name="Atomic Catalog Player", school="Ohio State", position="WR"))
        db.flush()
        return {"created": 1}

    def fail_ratings(*_args, **_kwargs):
        raise RuntimeError("forced rating reconciliation failure")

    monkeypatch.setattr(reconcile_preseason_player_data, "bootstrap", bootstrap_catalog)
    monkeypatch.setattr(reconcile_preseason_player_data, "sync_cfb27_players", fail_ratings)

    with pytest.raises(RuntimeError, match="forced rating reconciliation failure"):
        reconcile_preseason_player_data.reconcile(
            identities=tmp_path / "player-identities.csv",
            projections=tmp_path / "player-projections.csv",
            ratings=tmp_path / "ratings.csv",
            ratings_manifest=tmp_path / "ratings.manifest.json",
            season=2026,
            dry_run=False,
        )

    assert db_session.query(Player).filter_by(name="Atomic Catalog Player").count() == 0


def test_wayne_knight_postcondition_requires_one_current_265_point_identity(db_session):
    player = Player(
        name="Wayne Knight",
        school="UCLA",
        position="RB",
        sheet_source_sheet_id=f"canonical-preseason:2026:{TEST_SOURCE_BATCH}:Big10",
        sheet_projected_season_points=265.0,
        sheet_projection_stats={
            "rush_yards": 1300.0,
            "rush_tds": 12.0,
            "receptions": 28.0,
            "rec_yards": 230.0,
            "rec_tds": 2.0,
            "fpts": 265.0,
        },
    )
    db_session.add(player)
    db_session.flush()

    result = reconcile_preseason_player_data.verify_wayne_knight_postcondition(
        db_session, season=2026, source_batch_id=TEST_SOURCE_BATCH
    )

    assert result["canonical_player_id"] == player.id
    assert result["sheet_projected_season_points"] == 265.0
    assert result["draft_eligible"] is True


def test_dry_run_plans_without_flushing_or_consuming_a_primary_key(db_session, monkeypatch, tmp_path):
    monkeypatch.setattr(reconcile_preseason_player_data, "SessionLocal", lambda: nullcontext(db_session))
    monkeypatch.setattr(
        reconcile_preseason_player_data,
        "require_valid_source_directory",
        lambda _path: _approved_wayne_source_contract(),
    )
    monkeypatch.setattr(reconcile_preseason_player_data, "load_reviewed_cfb27_snapshot", lambda **_kwargs: object())

    monkeypatch.setattr(
        reconcile_preseason_player_data,
        "plan_bootstrap",
        lambda **_kwargs: {
            "reviewed_rows": 814,
            "eligible_players": 814,
            "created": 1,
            "updated": 813,
            "ratings_matched": 814,
            "source_batch_id": TEST_SOURCE_BATCH,
        },
    )
    monkeypatch.setattr(
        reconcile_preseason_player_data,
        "bootstrap",
        lambda **_kwargs: pytest.fail("dry runs must never invoke the mutating bootstrap"),
    )
    monkeypatch.setattr(
        reconcile_preseason_player_data,
        "planned_active_cfb27_identities",
        lambda **_kwargs: (("Wayne Knight", "UCLA", "RB"),),
    )
    monkeypatch.setattr(
        reconcile_preseason_player_data,
        "plan_cfb27_players",
        lambda *_args, **_kwargs: {"matched": 814, "missing": 0, "unmatched_approved": 0},
    )

    def fail_if_flushed(*_args, **_kwargs):
        raise AssertionError("dry-run reconciliation must not flush")

    event.listen(db_session, "before_flush", fail_if_flushed)
    try:
        result = reconcile_preseason_player_data.reconcile(
            identities=tmp_path / "player-identities.csv",
            projections=tmp_path / "player-projections.csv",
            ratings=tmp_path / "ratings.csv",
            ratings_manifest=tmp_path / "ratings.manifest.json",
            season=2026,
            dry_run=True,
        )
    finally:
        event.remove(db_session, "before_flush", fail_if_flushed)

    assert result["catalog"]["created"] == 1
    assert result["wayne_knight"]["would_create"] is True
    assert not db_session.new
    assert db_session.query(Player).filter_by(name="Wayne Knight").count() == 0


def test_plan_bootstrap_is_read_only_even_when_it_would_create_players(db_session, monkeypatch, tmp_path):
    existing = Player(
        name="Existing Player",
        school="Ohio State",
        position="WR",
        sheet_source_sheet_id="canonical-preseason:2026:approved-test-batch:Big10",
    )
    db_session.add(existing)
    db_session.commit()
    existing_key = bootstrap_canonical_player_data.identity_key("Existing Player", "Ohio State", "WR")
    created_key = bootstrap_canonical_player_data.identity_key("Created Player", "Ohio State", "WR")
    rating = Cfb27Rating(
        rank=1,
        position_rank=1,
        name="Existing Player",
        school="Ohio State",
        position="WR",
        overall=99,
    )
    source = bootstrap_canonical_player_data.CanonicalCatalogSource(
        source_contract={"approved_player_count": 2},
        source_batch_id=TEST_SOURCE_BATCH,
        projections_by_key={existing_key: {"PLAYER": "Existing Player"}, created_key: {"PLAYER": "Created Player"}},
        reviewed_rows=[
            {"NAME": "Existing Player", "SCHOOL": "Ohio State", "POSITION": "WR"},
            {"NAME": "Created Player", "SCHOOL": "Ohio State", "POSITION": "WR"},
        ],
        ratings_by_key={
            bootstrap_canonical_player_data.cfb27_identity_key(
                name="Existing Player", school="Ohio State", position="WR"
            ): rating,
        },
    )
    monkeypatch.setattr(bootstrap_canonical_player_data, "load_catalog_source", lambda **_kwargs: source)
    monkeypatch.setattr(bootstrap_canonical_player_data, "ensure_models_registered", lambda: None)

    def fail_if_flushed(*_args, **_kwargs):
        raise AssertionError("planning a bootstrap must not flush")

    event.listen(db_session, "before_flush", fail_if_flushed)
    try:
        result = bootstrap_canonical_player_data.plan_bootstrap(
            identities_path=tmp_path / "player-identities.csv",
            projections_path=tmp_path / "player-projections.csv",
            db=db_session,
        )
    finally:
        event.remove(db_session, "before_flush", fail_if_flushed)

    assert result == {
        "reviewed_rows": 2,
        "eligible_players": 2,
        "source_contract_approved_players": 2,
        "created": 1,
        "updated": 1,
        "ratings_matched": 1,
        "legacy_snapshot_players_excluded_from_current_pool": 0,
        "source_batch_id": TEST_SOURCE_BATCH,
    }
    assert not db_session.new
