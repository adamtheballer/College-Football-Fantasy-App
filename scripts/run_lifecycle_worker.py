from __future__ import annotations

import argparse
import logging
import os
import sys
import time

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.services.draft_service import process_expired_draft_picks_once
from collegefootballfantasy_api.app.services.trade_service import process_trade_offers_once
from collegefootballfantasy_api.app.services.waiver_service import process_waiver_claims_once
from collegefootballfantasy_api.app.services.worker_health import record_worker_heartbeat

logger = logging.getLogger("collegefootballfantasy_api.lifecycle_worker")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Process due draft, waiver, and trade lifecycle work.")
    parser.add_argument("--once", action="store_true", help="Run one lifecycle iteration and exit.")
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=settings.lifecycle_worker_interval_seconds,
        help="Delay between worker iterations.",
    )
    return parser.parse_args()


def run_once() -> dict[str, dict[str, int]]:
    with SessionLocal() as db:
        return {
            "drafts": process_expired_draft_picks_once(db),
            "waivers": process_waiver_claims_once(db),
            "trades": process_trade_offers_once(db),
        }


def main() -> None:
    args = parse_args()
    interval_seconds = max(1, args.interval_seconds)
    while True:
        try:
            result = run_once()
            with SessionLocal() as db:
                record_worker_heartbeat(db, worker_name="lifecycle_processor", success=True, details=result)
            logger.info("lifecycle_worker_iteration_complete", extra=result)
        except Exception:  # pragma: no cover - operational failure path
            with SessionLocal() as db:
                record_worker_heartbeat(db, worker_name="lifecycle_processor", success=False)
            logger.exception("lifecycle_worker_iteration_failed")
        if args.once:
            return
        time.sleep(interval_seconds)


if __name__ == "__main__":
    main()
