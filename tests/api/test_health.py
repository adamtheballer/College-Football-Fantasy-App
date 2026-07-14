
import subprocess
import sys

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from collegefootballfantasy_api.app.services.readiness import (
    check_alembic_readiness,
    get_alembic_heads,
)


def _reset_alembic_version(db_session, revision: str | None = None) -> None:
    db_session.execute(text("DROP TABLE IF EXISTS alembic_version"))
    if revision is not None:
        db_session.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        db_session.execute(text("INSERT INTO alembic_version (version_num) VALUES (:revision)"), {"revision": revision})
    db_session.commit()


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert response.headers["x-request-id"]


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
