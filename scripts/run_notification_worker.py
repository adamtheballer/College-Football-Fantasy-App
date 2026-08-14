"""Dedicated durable notification processor; intentionally separate from live scoring."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from uuid import uuid4

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.core.logging import configure_logging
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.services.notification_service import (
    notification_queue_health,
    process_due_notifications_once,
)
from collegefootballfantasy_api.app.services.worker_health import record_worker_heartbeat


logger = logging.getLogger("collegefootballfantasy_api.notification_worker")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Process the durable notification outbox.")
    parser.add_argument("--once", action="store_true", help="Run one processor iteration and exit.")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--interval-seconds", type=int, default=settings.notification_worker_interval_seconds)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    interval_seconds = max(1, args.interval_seconds)
    worker_id = f"notification_processor:{uuid4()}"
    configure_logging(settings.api_log_level)
    logger.info(
        "notification_worker_started push_enabled=%s email_enabled=%s provider=%s",
        settings.push_notifications_enabled,
        settings.email_enabled,
        settings.push_provider,
    )
    while True:
        try:
            with SessionLocal() as db:
                result = process_due_notifications_once(db, worker_id=worker_id, limit=args.limit)
                health = notification_queue_health(db)
                record_worker_heartbeat(
                    db,
                    worker_name="notification_processor",
                    success=True,
                    details={**health, **result},
                )
            logger.info("notification_worker_iteration_complete", extra=result)
        except Exception:  # pragma: no cover - operational path
            with SessionLocal() as db:
                record_worker_heartbeat(db, worker_name="notification_processor", success=False)
            logger.exception("notification_worker_iteration_failed")
        if args.once:
            return
        time.sleep(interval_seconds)


if __name__ == "__main__":
    main()
