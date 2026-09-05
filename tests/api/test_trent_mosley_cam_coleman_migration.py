from __future__ import annotations

import importlib.util
from pathlib import Path


MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "api"
    / "alembic"
    / "versions"
    / "0112_add_trent_mosley_and_correct_cam_coleman.py"
)


def load_migration_module():
    spec = importlib.util.spec_from_file_location("trent_mosley_cam_coleman_migration", MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_trent_mosley_and_cam_coleman_migration_uses_verified_components(monkeypatch):
    migration = load_migration_module()
    statements: list[str] = []
    monkeypatch.setattr(migration.op, "execute", statements.append)

    migration.upgrade()

    assert migration.down_revision == "0111_sync_cam_coleman_projection"
    assert len(statements) == 3

    trent_update, trent_insert, cam_update = statements
    assert "name = 'Trent Mosley'" in trent_update
    assert "school = 'USC'" in trent_update
    assert "sheet_projected_season_points = 245.5" in trent_update
    assert "'rush_yards', 55.0" in trent_update
    assert "'rush_tds', 1.0" in trent_update
    assert "'receptions', 65.0" in trent_update
    assert "'rec_yards', 1150.0" in trent_update
    assert "'rec_tds', 9.0" in trent_update
    assert "'fpts', 245.5" in trent_update
    assert "INSERT INTO players" in trent_insert
    assert "WHERE NOT EXISTS" in trent_insert

    assert "name = 'Cam Coleman'" in cam_update
    assert "sheet_projected_season_points = 284.6" in cam_update
    assert "'rush_tds', 0.0" in cam_update
    assert "'receptions', 79.0" in cam_update
    assert "'rec_tds', 13.0" in cam_update
    assert "'fpts', 284.6" in cam_update
