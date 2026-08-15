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
from collegefootballfantasy_api.app.db.model_registry import ensure_models_registered
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.services.notification_service import (
    notification_queue_health,
    process_due_notifications_once,
)
from collegefootballfantasy_api.app.services.worker_health import record_worker_heartbeat


logger = logging.getLogger("collegefootballfantasy_api.notification_worker")


def log_iteration_result(result: dict[str, int], health: dict[str, int | str | None]) -> None:
    """Classify only safe aggregate worker outcomes at their operational severity."""
    claimed = int(result.get("claimed", 0))
    delivered = int(result.get("delivered", 0))
    accepted = int(result.get("provider_accepted", 0))
    retried = int(result.get("retried", 0))
    failed = int(result.get("failed", 0))
    pending = int(health.get("pending", 0) or 0)
    retry = int(health.get("retry", 0) or 0)
    dead_letter = int(health.get("dead_letter", 0) or 0)
    message = (
        "notification_worker_iteration claimed=%s delivered=%s provider_accepted=%s "
        "retried=%s failed=%s pending=%s retry=%s dead_letter=%s"
    )
    values = (claimed, delivered, accepted, retried, failed, pending, retry, dead_letter)
    if failed or dead_letter:
        logger.error(message, *values)
    elif retried or retry:
        logger.warning(message, *values)
    else:
        logger.info(message, *values)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Process the durable notification outbox.")
    parser.add_argument("--once", action="store_true", help="Run one processor iteration and exit.")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--interval-seconds", type=int, default=settings.notification_worker_interval_seconds)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    # Unlike the API process, this worker does not import routes as a side
    # effect. Register every relationship target before the first ORM query
    # so a clean worker process cannot fail mapper configuration at runtime.
    ensure_models_registered()
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
            log_iteration_result(result, health)
        except Exception:  # pragma: no cover - operational path
            with SessionLocal() as db:
                record_worker_heartbeat(db, worker_name="notification_processor", success=False)
            logger.exception("notification_worker_iteration_failed")
        if args.once:
            return
        time.sleep(interval_seconds)


if __name__ == "__main__":
    main()
