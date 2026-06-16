
from sqlalchemy import text


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_requires_migration_table(client):
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["detail"]["database"] == "ok"
    assert response.json()["detail"]["migrations"] == "missing"


def test_readiness_reports_database_and_migration_status(client, db_session):
    db_session.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
    db_session.execute(text("INSERT INTO alembic_version (version_num) VALUES ('test_revision')"))
    db_session.commit()

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "ok",
        "migrations": "ok",
        "alembic_version": "test_revision",
    }
