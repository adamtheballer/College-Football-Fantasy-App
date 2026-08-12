from __future__ import annotations

import argparse
import logging
import os
import time
from dataclasses import dataclass

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.services.espn_live_polling_service import run_espn_shadow_poll_iteration
from collegefootballfantasy_api.app.services.live_scoring_service import process_one_scoring_work_item
from collegefootballfantasy_api.app.services.worker_health import record_worker_heartbeat

logger = logging.getLogger("collegefootballfantasy_api.scoring_worker")


@dataclass(frozen=True)
class WorkerSchedule:
    mode: str
    interval_seconds: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Production scoring worker process.")
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--league-id", type=int, default=None)
    parser.add_argument("--provider", default=settings.scoring_provider)
    parser.add_argument(
        "--mode",
        choices=("live", "postgame", "correction"),
        default="live",
        help="Cadence profile: live game window, postgame reconciliation, or next-day correction sweep.",
    )
    parser.add_argument("--once", action="store_true", help="Run one worker iteration and exit.")
    return parser.parse_args()


def schedule_for_mode(mode: str) -> WorkerSchedule:
    # The worker checks durable due work every ~30 seconds while ESPN shadow
    # polling is enabled. Per-game state still caps active ESPN calls at 180
    # seconds, so this does not turn into a per-player/provider request loop.
    if settings.espn_live_scoring_enabled:
        return WorkerSchedule(mode=mode, interval_seconds=settings.espn_live_scoring_worker_interval_seconds)
    if mode == "postgame":
        return WorkerSchedule(mode=mode, interval_seconds=settings.scoring_worker_interval_postgame_seconds)
    if mode == "correction":
        return WorkerSchedule(mode=mode, interval_seconds=settings.scoring_worker_interval_correction_seconds)
    return WorkerSchedule(mode=mode, interval_seconds=settings.scoring_worker_interval_live_seconds)


def run_iteration(args: argparse.Namespace) -> None:
    if settings.scoring_mode not in {"enabled", "shadow"}:
        raise RuntimeError("Scoring worker cannot run while SCORING_MODE=disabled.")
    worker_id = f"scoring-processor:{os.getpid()}"
    espn_result = None
    if settings.espn_live_scoring_enabled:
        if not settings.scoring_shadow_enabled:
            raise RuntimeError("ESPN live polling requires SCORING_MODE=shadow.")
        # This helper commits its short claim transactions before each ESPN
        # request, so no database lock or transaction spans provider I/O.
        espn_result = run_espn_shadow_poll_iteration(
            session_factory=SessionLocal,
            season=args.season,
            week=args.week,
        )
    with SessionLocal() as db:
        try:
            item = process_one_scoring_work_item(db, worker_id=worker_id)
            db.commit()
        except Exception:
            # The work item is deliberately failed/dead-lettered inside the
            # processor. Persist that durable state before the retry loop.
            db.commit()
            raise
        record_worker_heartbeat(
            db,
            worker_name="scoring_processor",
            success=True,
            details={
                "season": args.season,
                "week": args.week,
                "league_id": args.league_id,
                "mode": args.mode,
                "work_item_id": item.id if item else None,
                "provider_polling": bool(settings.espn_live_scoring_enabled),
                "espn": (
                    {
                        "states_created": espn_result.states_created,
                        "scoreboard_games": espn_result.scoreboard_games,
                        "detail_requests": espn_result.detail_requests,
                        "detail_ingested": espn_result.detail_ingested,
                        "failures": espn_result.failures,
                    }
                    if espn_result is not None
                    else None
                ),
            },
        )


def run_with_retries(args: argparse.Namespace) -> None:
    attempts = max(1, settings.scoring_worker_retry_max_attempts)
    base_sleep = max(1, settings.scoring_worker_retry_base_seconds)
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            run_iteration(args)
            return
        except Exception as exc:  # pragma: no cover - provider/DB failure mode depends on runtime
            last_error = exc
            logger.warning(
                "scoring_worker_attempt_failed",
                extra={
                    "attempt": attempt,
                    "max_attempts": attempts,
                    "season": args.season,
                    "week": args.week,
                    "league_id": args.league_id,
                    "provider": args.provider,
                    "mode": args.mode,
                    "error": str(exc),
                },
            )
            if attempt < attempts:
                time.sleep(base_sleep * (2 ** (attempt - 1)))
    if last_error is not None:
        with SessionLocal() as db:
            record_worker_heartbeat(
                db,
                worker_name="scoring_processor",
                success=False,
                details={"season": args.season, "week": args.week, "league_id": args.league_id, "mode": args.mode},
            )
        raise last_error


def main() -> None:
    if settings.scoring_mode not in {"enabled", "shadow"}:
        raise SystemExit("Scoring worker cannot start while SCORING_MODE=disabled.")
    args = parse_args()
    schedule = schedule_for_mode(args.mode)
    logger.info(
        "scoring_worker_started",
        extra={
            "season": args.season,
            "week": args.week,
            "league_id": args.league_id,
            "provider": args.provider,
            "mode": args.mode,
            "interval_seconds": schedule.interval_seconds,
            "once": args.once,
        },
    )
    while True:
        started_at = time.monotonic()
        run_with_retries(args)
        if args.once:
            return
        elapsed = time.monotonic() - started_at
        time.sleep(max(0, schedule.interval_seconds - elapsed))


if __name__ == "__main__":
    main()
