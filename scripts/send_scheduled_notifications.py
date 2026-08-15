"""Compatibility entry point for one notification-worker iteration.

The prior implementation posted directly to Expo and Resend, bypassing the
durable delivery-attempt records. Keep the script name for operators, but route
all work through the canonical outbox processor.
"""

from __future__ import annotations

import argparse
import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.services.notification_service import (
    notification_queue_health,
    process_due_notifications_once,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Process due durable notification events once.")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--dry-run", action="store_true", help="Print queue health without delivering notifications.")
    args = parser.parse_args()
    with SessionLocal() as db:
        if args.dry_run:
            print(notification_queue_health(db))
            return
        print(process_due_notifications_once(db, worker_id="notification_once", limit=args.limit))


if __name__ == "__main__":
    main()
