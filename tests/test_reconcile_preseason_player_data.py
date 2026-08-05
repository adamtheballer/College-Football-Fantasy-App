from contextlib import nullcontext
from pathlib import Path

import pytest

from collegefootballfantasy_api.app.models.player import Player
from scripts import reconcile_preseason_player_data
from scripts.audit_preseason_source_contract import (
    WAYNE_KNIGHT_APPROVED_PROJECTION_SNAPSHOT_SHA256,
    WAYNE_KNIGHT_APPROVED_SOURCE_BATCH,
)


def _approved_wayne_source_contract():
    return {
        "wayne_knight_projection_integrity": {
            "projection_snapshot_sha256": WAYNE_KNIGHT_APPROVED_PROJECTION_SNAPSHOT_SHA256,
        }
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
        sheet_source_sheet_id=f"canonical-preseason:2026:{WAYNE_KNIGHT_APPROVED_SOURCE_BATCH}:Big10",
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

    result = reconcile_preseason_player_data.verify_wayne_knight_postcondition(db_session, season=2026)

    assert result["canonical_player_id"] == player.id
    assert result["sheet_projected_season_points"] == 265.0
    assert result["draft_eligible"] is True


def test_dry_run_rolls_back_when_wayne_knight_projection_postcondition_fails(db_session, monkeypatch, tmp_path):
    monkeypatch.setattr(reconcile_preseason_player_data, "SessionLocal", lambda: nullcontext(db_session))
    monkeypatch.setattr(
        reconcile_preseason_player_data,
        "require_valid_source_directory",
        lambda _path: _approved_wayne_source_contract(),
    )
    monkeypatch.setattr(reconcile_preseason_player_data, "load_reviewed_cfb27_snapshot", lambda **_kwargs: object())

    def bootstrap_catalog(**kwargs):
        db = kwargs["db"]
        db.add(
            Player(
                name="Wayne Knight",
                school="UCLA",
                position="RB",
                sheet_source_sheet_id="canonical-preseason:2026:stale-batch:Big10",
                sheet_projected_season_points=12.5,
            )
        )
        db.flush()
        return {"created": 1}

    monkeypatch.setattr(reconcile_preseason_player_data, "bootstrap", bootstrap_catalog)

    with pytest.raises(RuntimeError, match="Wayne Knight projection source batch mismatch"):
        reconcile_preseason_player_data.reconcile(
            identities=tmp_path / "player-identities.csv",
            projections=tmp_path / "player-projections.csv",
            ratings=tmp_path / "ratings.csv",
            ratings_manifest=tmp_path / "ratings.manifest.json",
            season=2026,
            dry_run=True,
        )

    assert db_session.query(Player).filter_by(name="Wayne Knight").count() == 0
