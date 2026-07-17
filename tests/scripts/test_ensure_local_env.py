from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "ensure_local_env.py"


def load_module():
    spec = importlib.util.spec_from_file_location("ensure_local_env", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_creates_worktree_env_and_enables_espn_history(monkeypatch, tmp_path):
    module = load_module()
    env_example = tmp_path / ".env.example"
    env_file = tmp_path / ".env"
    env_example.write_text("DATABASE_URL=postgresql://local\nESPN_HISTORICAL_STATS_ENABLED=false\n")
    monkeypatch.setattr(module, "ENV_EXAMPLE_FILE", env_example)
    monkeypatch.setattr(module, "ENV_FILE", env_file)
    monkeypatch.setattr(sys, "argv", ["ensure_local_env.py", "--enable-espn-historical-stats"])

    assert module.main() == 0
    assert env_file.read_text() == (
        "DATABASE_URL=postgresql://local\n"
        "ESPN_HISTORICAL_STATS_ENABLED=true\n"
        "COMPOSE_PROJECT_NAME=cff_local\n"
        "DB_PORT=5433\n"
        "API_PORT=8000\n"
        "WEB_PORT=8080\n"
    )


def test_preserves_existing_values_when_enabling_espn_history(monkeypatch, tmp_path):
    module = load_module()
    env_file = tmp_path / ".env"
    env_file.write_text("JWT_SECRET_KEY=local-secret\n")
    monkeypatch.setattr(module, "ENV_FILE", env_file)
    monkeypatch.setattr(sys, "argv", ["ensure_local_env.py", "--enable-espn-historical-stats"])

    assert module.main() == 0
    assert env_file.read_text() == (
        "JWT_SECRET_KEY=local-secret\n"
        "COMPOSE_PROJECT_NAME=cff_local\n"
        "DB_PORT=5433\n"
        "API_PORT=8000\n"
        "WEB_PORT=8080\n"
        "ESPN_HISTORICAL_STATS_ENABLED=true\n"
    )


def test_migrates_only_the_legacy_local_database_default(monkeypatch, tmp_path):
    module = load_module()
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/collegefootballfantasy\n"
    )
    monkeypatch.setattr(module, "ENV_FILE", env_file)
    monkeypatch.setattr(sys, "argv", ["ensure_local_env.py"])

    assert module.main() == 0
    assert env_file.read_text() == (
        "DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/collegefootballfantasy\n"
        "COMPOSE_PROJECT_NAME=cff_local\n"
        "DB_PORT=5433\n"
        "API_PORT=8000\n"
        "WEB_PORT=8080\n"
    )


def test_preserves_explicit_persistent_stack_values(monkeypatch, tmp_path):
    module = load_module()
    env_file = tmp_path / ".env"
    env_file.write_text("COMPOSE_PROJECT_NAME=cff_feature_schema\nDB_PORT=55440\n")
    monkeypatch.setattr(module, "ENV_FILE", env_file)
    monkeypatch.setattr(sys, "argv", ["ensure_local_env.py"])

    assert module.main() == 0
    assert env_file.read_text() == (
        "COMPOSE_PROJECT_NAME=cff_feature_schema\n"
        "DB_PORT=55440\n"
        "API_PORT=8000\n"
        "WEB_PORT=8080\n"
    )
