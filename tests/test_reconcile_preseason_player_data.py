from contextlib import nullcontext
from pathlib import Path

import pytest

from collegefootballfantasy_api.app.models.player import Player
from scripts import reconcile_preseason_player_data


def test_atomic_reconciler_rolls_back_catalog_when_rating_phase_fails(db_session, monkeypatch, tmp_path):
    monkeypatch.setattr(reconcile_preseason_player_data, "SessionLocal", lambda: nullcontext(db_session))
    monkeypatch.setattr(reconcile_preseason_player_data, "require_valid_source_directory", lambda _path: None)
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
