"""Certify native push migration on disposable localhost PostgreSQL only.

Creates and drops a random sibling database; never consumes DATABASE_URL.
"""
import os
from sqlalchemy import MetaData, Table, create_engine, inspect, text
from sqlalchemy.engine import make_url
from scripts.certify_postseason_migrations import _require_disposable_postgres, _run_alembic, _temporary_database

PREVIOUS = "0117_app_review_request"
HEAD = "0118_native_push_delivery"


def main():
    raw = os.environ.get("NATIVE_PUSH_TEST_DATABASE_URL")
    if not raw:
        raise SystemExit("Set NATIVE_PUSH_TEST_DATABASE_URL to disposable local PostgreSQL")
    base = make_url(raw)
    _require_disposable_postgres(base)
    if base.host not in {"localhost", "127.0.0.1", "::1"} or not (base.database or "").startswith("cff_push_"):
        raise SystemExit("Requires localhost and cff_push_* database; refusing other targets")
    with _temporary_database(base) as url:
        _run_alembic(url, "upgrade", PREVIOUS)
        engine = create_engine(url)
        try:
            with engine.begin() as db:
                user = db.scalar(text("""INSERT INTO users (email, first_name, password_hash, api_token, is_active, is_admin, failed_login_attempts, auth_version)
                    VALUES ('push-migration@example.com', 'Migration', 'test-only', 'push-migration-test-only', TRUE, FALSE, 0, 1) RETURNING id"""))
                league = db.scalar(text("""INSERT INTO leagues (name, platform, scoring_type, season_year, max_teams, is_private, status)
                    VALUES ('Push Migration', 'custom', 'espn_full_ppr', 2026, 4, TRUE, 'pre_draft') RETURNING id"""))
                # Preserve disabled email and global push settings across upgrade.
                table = Table("notification_preferences", MetaData(), autoload_with=db)
                values = {column.name: True for column in table.columns if not column.nullable and column.type.python_type is bool}
                values.update(user_id=user, user_key=str(user), email_enabled=False, push_enabled=False, timezone="UTC")
                db.execute(table.insert().values(**values))
                event = db.scalar(text("""INSERT INTO scheduled_notifications (league_id, user_id, notification_type, event_type, event_key, scheduled_for, status, scope, category)
                    VALUES (:league, :user, 'DRAFT_START', 'DRAFT_START', 'pre-rollout', now()-interval '1 day', 'pending', 'league_participant', 'DRAFT') RETURNING id"""), {"league": league, "user": user})
                db.execute(text("""INSERT INTO notification_delivery_attempts (scheduled_notification_id, user_id, channel, attempt_number, status)
                    VALUES (:event, :user, 'push', 1, 'pending'), (:event, :user, 'email', 1, 'pending')"""), {"event": event, "user": user})
            _run_alembic(url, "upgrade", HEAD)
            with engine.connect() as db:
                assert db.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
                pref = db.execute(text("SELECT push_enabled, email_enabled, push_drafts, push_matchups, push_injuries, push_major_news FROM notification_preferences")).one()
                assert tuple(pref) == (False, False, True, True, True, False)
                assert dict(db.execute(text("SELECT channel, status FROM notification_delivery_attempts")).all()) == {"push": "expired", "email": "pending"}
                assert db.scalar(text("SELECT count(*) FROM news_announcements")) == 0
                assert db.scalar(text("SELECT count(*) FROM scheduled_notifications")) == 1
            indexes = {item["name"] for item in inspect(engine).get_indexes("notification_delivery_attempts")}
            assert "uq_notification_attempt_channel" in indexes
            assert "uq_push_tokens_active_installation" in {item["name"] for item in inspect(engine).get_indexes("push_tokens")}
            assert any(item["referred_table"] == "push_tokens" and item["options"].get("ondelete") == "RESTRICT" for item in inspect(engine).get_foreign_keys("notification_delivery_attempts"))
            _run_alembic(url, "downgrade", PREVIOUS)
            _run_alembic(url, "upgrade", HEAD)
            with engine.begin() as db:
                db.execute(text("INSERT INTO news_announcements (created_by, title, body, audience, status) VALUES (:user, 'Retained', 'Retained audit', '{}', 'draft')"), {"user": user})
            try:
                _run_alembic(url, "downgrade", PREVIOUS)
            except RuntimeError as error:
                assert "retain the push ledger" in str(error)
            else:
                raise AssertionError("Used ledger must block destructive downgrade")
            with engine.connect() as db:
                assert db.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
                assert db.scalar(text("SELECT count(*) FROM news_announcements")) == 1
            _run_alembic(url, "upgrade", "head")
            print(_run_alembic(url, "check").strip())
            print("PASS: full history, populated upgrade, opt-in defaults/email preservation, historical push suppression, indexes/FK, unused downgrade/re-upgrade, retained-ledger downgrade refusal and model parity")
        finally:
            engine.dispose()


if __name__ == "__main__":
    main()
