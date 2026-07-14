from __future__ import annotations

import argparse
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.models.scoring_run import ScoringRun
from scripts.sync_live_scores import run_once

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
    if mode == "postgame":
        return WorkerSchedule(mode=mode, interval_seconds=settings.scoring_worker_interval_postgame_seconds)
    if mode == "correction":
        return WorkerSchedule(mode=mode, interval_seconds=settings.scoring_worker_interval_correction_seconds)
    return WorkerSchedule(mode=mode, interval_seconds=settings.scoring_worker_interval_live_seconds)


def record_worker_dead_letter(
    *,
    provider: str,
    season: int,
    week: int,
    league_id: int | None,
    mode: str,
    error: Exception,
) -> None:
    with SessionLocal() as db:
        db.add(
            ScoringRun(
                league_id=league_id,
                season=season,
                week=week,
                provider=provider,
                status="dead_letter",
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                error_message=f"{mode} worker exhausted retries: {str(error)[:900]}",
            )
        )
        db.commit()


def run_iteration(args: argparse.Namespace) -> None:
    live_args = argparse.Namespace(
        season=args.season,
        week=args.week,
        league_id=args.league_id,
        provider=args.provider,
        watch=False,
        interval_seconds=schedule_for_mode(args.mode).interval_seconds,
    )
    run_once(live_args)


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
        record_worker_dead_letter(
            provider=args.provider,
            season=args.season,
            week=args.week,
            league_id=args.league_id,
            mode=args.mode,
            error=last_error,
        )
        raise last_error


def main() -> None:
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
