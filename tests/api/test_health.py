
import subprocess
import sys

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.services.readiness import (
    DEFAULT_ALEMBIC_INI,
    check_alembic_readiness,
    get_alembic_heads,
)


def _reset_alembic_version(db_session, revision: str | None = None) -> None:
    db_session.execute(text("DROP TABLE IF EXISTS alembic_version"))
    if revision is not None:
        db_session.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        db_session.execute(text("INSERT INTO alembic_version (version_num) VALUES (:revision)"), {"revision": revision})
    db_session.commit()


def test_all_alembic_revisions_fit_the_legacy_version_column():
    script = ScriptDirectory.from_config(Config(str(DEFAULT_ALEMBIC_INI)))
    oversized = [revision.revision for revision in script.walk_revisions() if len(revision.revision) > 32]

    assert oversized == []


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert response.headers["x-request-id"]
    assert response.headers["x-cff-process-instance"]


def test_runtime_identity_reports_safe_process_and_database_identifiers(client, db_session):
    head = get_alembic_heads()[0]
    _reset_alembic_version(db_session, head)

    response = client.get("/health/identity")

    assert response.status_code == 200
    payload = response.json()
    assert payload["api_process_instance_uuid"]
    assert payload["runtime_id"] == settings.runtime_id
    assert payload["runtime_mode"] == settings.runtime_mode
    assert payload["web_git_sha"] == settings.web_git_sha
    assert payload["worker_git_sha"] == settings.worker_git_sha
    assert payload["scoring_mode"] == settings.scoring_mode
    assert payload["sportsdata_enabled"] == settings.sportsdata_enabled
    assert payload["email_enabled"] is settings.email_enabled
    assert payload["scoring_worker_expected"] is settings.scoring_worker_expected
    assert payload["provider_polling_expected"] is settings.provider_polling_expected
    assert payload["player_dataset_version"] == settings.player_dataset_version
    assert payload["projection_dataset_version"] == settings.projection_dataset_version
    assert payload["cfb27_rating_dataset_version"] == settings.cfb27_rating_dataset_version
    assert payload["database_instance_uuid"]
    assert payload["alembic_version"] == [head]
    assert payload["alembic_revision"] == head
    assert payload["readiness_status"] == "ready"
    assert "database_host" not in payload
    assert "database_url" not in payload


def test_runtime_reports_safe_database_identity(client, db_session):
    head = get_alembic_heads()[0]
    _reset_alembic_version(db_session, head)

    response = client.get("/health/runtime")

    assert response.status_code == 200
    payload = response.json()
    assert payload["environment"] == settings.environment
    assert payload["runtime_mode"] == settings.runtime_mode
    assert payload["web_git_sha"] == settings.web_git_sha
    assert payload["worker_git_sha"] == settings.worker_git_sha
    assert payload["player_dataset_version"] == settings.player_dataset_version
    assert payload["projection_dataset_version"] == settings.projection_dataset_version
    assert payload["cfb27_rating_dataset_version"] == settings.cfb27_rating_dataset_version
    assert payload["database_instance_uuid"]
    assert payload["alembic_version"] == [head]
    assert payload["alembic_revision"] == head
    assert payload["scoring_mode"] == settings.scoring_mode
    assert payload["email_enabled"] is settings.email_enabled
    assert payload["scoring_worker_expected"] is settings.scoring_worker_expected
    assert payload["provider_polling_expected"] is settings.provider_polling_expected
    assert "database_url" not in payload


def test_runtime_remains_public_and_safe_in_production(client, db_session, monkeypatch):
    head = get_alembic_heads()[0]
    _reset_alembic_version(db_session, head)
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "scoring_mode", "disabled")
    monkeypatch.setattr(settings, "sportsdata_enabled", False)

    response = client.get("/health/runtime")

    assert response.status_code == 200
    assert response.json()["environment"] == "production"
    assert response.json()["scoring_mode"] == "disabled"
    assert response.json()["sportsdata_enabled"] is False
    assert response.json()["email_enabled"] is False
    assert response.json()["scoring_worker_expected"] is False
    assert response.json()["provider_polling_expected"] is False


def test_readiness_returns_200_when_database_matches_alembic_head(client, db_session):
    head = get_alembic_heads()[0]
    _reset_alembic_version(db_session, head)

    response = client.get("/health/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["database"] == "ready"
    assert payload["migrations"] == "ready"
    assert payload["current_revisions"] == [head]
    assert payload["expected_revisions"] == [head]


def test_readiness_returns_503_when_alembic_table_missing(client, db_session):
    _reset_alembic_version(db_session)

    response = client.get("/health/ready")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert payload["database"] == "ready"
    assert payload["migrations"] == "missing"
    assert payload["current_revisions"] == []


def test_readiness_returns_503_when_database_is_behind_head(client, db_session):
    _reset_alembic_version(db_session, "0001_initial")

    response = client.get("/health/ready")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert payload["database"] == "ready"
    assert payload["migrations"] == "out_of_date"
    assert payload["current_revisions"] == ["0001_initial"]


def test_readiness_helper_reports_unreachable_database():
    class BrokenSession:
        def execute(self, *_args, **_kwargs):
            raise SQLAlchemyError("connection failed")

    readiness = check_alembic_readiness(BrokenSession())  # type: ignore[arg-type]

    assert readiness.status == "not_ready"
    assert readiness.database == "unreachable"
    assert readiness.migrations == "unknown"


def test_check_alembic_head_script_passes_and_fails(tmp_path):
    head = get_alembic_heads()[0]
    db_path = tmp_path / "ready.db"
    database_url = f"sqlite:///{db_path}"

    import sqlite3

    with sqlite3.connect(db_path) as connection:
        connection.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        connection.execute("INSERT INTO alembic_version (version_num) VALUES (?)", (head,))

    passed = subprocess.run(
        [
            sys.executable,
            "scripts/check_alembic_head.py",
            "--database-url",
            database_url,
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert passed.returncode == 0
    assert '"status": "ready"' in passed.stdout

    with sqlite3.connect(db_path) as connection:
        connection.execute("UPDATE alembic_version SET version_num = ?", ("0001_initial",))

    failed = subprocess.run(
        [
            sys.executable,
            "scripts/check_alembic_head.py",
            "--database-url",
            database_url,
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert failed.returncode == 1
    assert '"migrations": "out_of_date"' in failed.stdout
