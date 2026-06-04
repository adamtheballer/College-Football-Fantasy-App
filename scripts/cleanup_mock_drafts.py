from __future__ import annotations

from api.app.db.session import SessionLocal
from api.app.services.mock_draft_service import cleanup_expired_mock_drafts


def main() -> None:
    with SessionLocal() as db:
        counts = cleanup_expired_mock_drafts(db)
        db.commit()
        print(
            "cleanup_mock_drafts "
            f"sessions={counts['sessions']} picks={counts['picks']} "
            f"participants={counts['participants']} events={counts['events']}"
        )


if __name__ == "__main__":
    main()
