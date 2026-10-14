"""Set a single explicitly named local browser-test account's cooldown.

Test-only CLI; no production reset endpoint or forced prompt is shipped.
"""
import argparse
import os

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("account_id", type=int)
    parser.add_argument("--remaining-seconds", type=int, default=-86400)
    parser.add_argument("--legacy-avatar", action="store_true")
    args = parser.parse_args()
    raw = os.environ.get("CFF_NAME_CHANGE_E2E_DATABASE_URL", "")
    url = make_url(raw)
    if url.host not in {"localhost", "127.0.0.1", "::1"} or not (url.database or "").startswith("cff_app_review_") or os.getenv("ENVIRONMENT", "development").lower() in {"production", "staging"}:
        raise SystemExit("Only isolated local cff_app_review_* test databases are allowed")
    engine = create_engine(url)
    try:
        with engine.begin() as db:
            result = db.execute(text("""UPDATE users SET
                manager_name_changed_at=clock_timestamp() - INTERVAL '168 hours' + :seconds * INTERVAL '1 second',
                avatar_url=CASE WHEN :legacy THEN 'http://legacy.example.com/avatar.jpg' ELSE avatar_url END
                WHERE id=:id AND email LIKE 'name-e2e-%@example.com'"""),
                {"id": args.account_id, "seconds": args.remaining_seconds, "legacy": args.legacy_avatar})
            assert result.rowcount == 1, "Not an explicitly designated name-e2e account"
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
