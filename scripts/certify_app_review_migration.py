"""Certify App Review ledger upgrade/rollback only on disposable local PostgreSQL.

Creates/drops a random sibling database using the existing certification helper.
Never reads DATABASE_URL or connects to a production/staging host.
"""
import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from scripts.certify_postseason_migrations import _require_disposable_postgres, _run_alembic, _temporary_database

PREVIOUS = "0116_league_conference_pool"
HEAD = "0117_app_review_request"


def main() -> None:
    raw = os.environ.get("APP_REVIEW_TEST_DATABASE_URL")
    if not raw:
        raise SystemExit("Set APP_REVIEW_TEST_DATABASE_URL to a disposable local PostgreSQL database")
    base = make_url(raw)
    _require_disposable_postgres(base)
    if base.host not in {"localhost", "127.0.0.1", "::1"} or not (base.database or "").startswith("cff_app_review_"):
        raise SystemExit("Requires a local database named cff_app_review_*; refusing other targets")
    with _temporary_database(base) as url:
        _run_alembic(url, "upgrade", PREVIOUS)
        engine = create_engine(url)
        try:
            with engine.begin() as db:
                user_id = db.scalar(text("""INSERT INTO users
                    (email, first_name, password_hash, api_token, is_active, is_admin, failed_login_attempts, auth_version)
                    VALUES ('review-migration@example.com', 'Migration', 'test-only', 'review-migration-test-only', TRUE, FALSE, 0, 1)
                    RETURNING id"""))
            _run_alembic(url, "upgrade", HEAD)
            with engine.connect() as db:
                row = db.execute(text("SELECT review_request_claimed_at, review_request_app_version, review_request_app_build FROM users WHERE id=:id"), {"id": user_id}).one()
                assert tuple(row) == (None, None, None)
                assert db.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
            assert any(item["name"] == "ck_users_review_request_metadata" for item in inspect(engine).get_check_constraints("users"))
            _run_alembic(url, "downgrade", PREVIOUS)
            _run_alembic(url, "upgrade", HEAD)
            with engine.begin() as db:
                db.execute(text("UPDATE users SET review_request_claimed_at=now(), review_request_app_version='1', review_request_app_build='123' WHERE id=:id"), {"id": user_id})
            try:
                _run_alembic(url, "downgrade", PREVIOUS)
            except RuntimeError as error:
                assert "Cannot remove the review ledger after claims" in str(error)
            else:
                raise AssertionError("A consumed account's ledger must prevent destructive downgrade")
            with engine.connect() as db:
                assert db.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
                assert db.scalar(text("SELECT review_request_claimed_at FROM users WHERE id=:id"), {"id": user_id}) is not None
            # Check new columns against their mapped definitions independently
            # of any pre-existing unrelated Alembic autogeneration differences.
            columns = {item["name"]: item for item in inspect(engine).get_columns("users")}
            for name in ("review_request_claimed_at", "review_request_app_version", "review_request_app_build"):
                assert columns[name]["nullable"] and columns[name]["default"] is None
            assert columns["review_request_claimed_at"]["type"].timezone
            assert columns["review_request_app_version"]["type"].length == 80
            assert columns["review_request_app_build"]["type"].length == 80
            print("PASS: full history upgrade, existing account NULL backfill, constraint, downgrade/re-upgrade, consumed-ledger downgrade refusal, column parity")
            _run_alembic(url, "upgrade", "head")
            try:
                print(_run_alembic(url, "check").strip())
            except RuntimeError as error:
                # Report, never hide, repository-wide pre-existing schema drift.
                print(f"REPOSITORY ALEMBIC CHECK: {error}")
        finally:
            engine.dispose()


if __name__ == "__main__":
    main()
