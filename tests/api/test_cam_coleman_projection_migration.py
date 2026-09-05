import importlib.util
from pathlib import Path


def _load_migration():
    migration_path = (
        Path(__file__).resolve().parents[2]
        / "api"
        / "alembic"
        / "versions"
        / "0111_sync_cam_coleman_projection.py"
    )
    spec = importlib.util.spec_from_file_location("cam_coleman_projection_migration", migration_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cam_coleman_projection_migration_uses_verified_components(monkeypatch):
    migration = _load_migration()
    statements: list[str] = []
    monkeypatch.setattr(migration.op, "execute", statements.append)

    migration.upgrade()

    assert migration.down_revision == "0110_player_popularity"
    assert len(statements) == 1
    statement = statements[0]
    assert "sheet_projected_season_points = 281.6" in statement
    assert "'rec_yards', 1250.0" in statement
    assert "'rec_tds', 12.0" in statement
    assert "'receptions', 76.0" in statement
    assert "'rush_yards', 26.0" in statement
    assert "'rush_tds', 1.0" in statement
    assert "'fpts', 281.6" in statement
    assert "name = 'Cam Coleman'" in statement
    assert "school = 'Texas'" in statement
    assert "UPPER(position) = 'WR'" in statement
    assert "sheet_source_sheet_id LIKE 'canonical-preseason:2026:%'" in statement
