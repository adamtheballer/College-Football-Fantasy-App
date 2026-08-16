"""Durable ESPN alpha scoring scheduler.

This process wakes frequently enough to find due work but all provider calls
remain governed by the durable 180-second per-game lease in
``espn_live_scoring``.  It intentionally derives season/week from the stored
schedule rather than requiring an operator to edit a command every Saturday.
"""

from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime, timedelta, timezone

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.db.model_registry import ensure_models_registered
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.integrations.espn import ESPNClient
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from collegefootballfantasy_api.app.services.espn_live_scoring import EspnCycleResult, run_espn_scoring_cycle
from collegefootballfantasy_api.app.services.live_scoring_readiness import scoring_operations_report
from collegefootballfantasy_api.app.services.worker_health import record_worker_heartbeat


logger = logging.getLogger("collegefootballfantasy_api.espn_scoring_worker")
DISCOVERY_WAKE_SECONDS = 30


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the durable ESPN alpha scoring scheduler.")
    parser.add_argument("--once", action="store_true", help="Run one discovery/claim iteration and exit.")
    parser.add_argument("--interval-seconds", type=int, default=DISCOVERY_WAKE_SECONDS)
    return parser.parse_args()


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def resolve_scoring_window(db, *, now: datetime | None = None) -> tuple[int, int] | None:
    """Resolve the live or next scheduled CFB week from verified schedule rows.

    A schedule gap results in no provider traffic; the worker never guesses a
    season/week merely because the calendar says it is Saturday.
    """

    current = _as_utc(now or datetime.now(timezone.utc))
    rows = (
        db.query(TeamSchedule)
        .filter(
            TeamSchedule.kickoff_at.isnot(None),
            TeamSchedule.is_bye.is_(False),
            TeamSchedule.kickoff_at >= current - timedelta(hours=12),
            TeamSchedule.kickoff_at <= current + timedelta(days=8),
        )
        .order_by(TeamSchedule.kickoff_at.asc(), TeamSchedule.id.asc())
        .all()
    )
    if not rows:
        return None

    # Prefer the most recently started possible game window, then the nearest
    # verified upcoming kickoff.  Duplicate home/away schedule rows collapse
    # naturally to the same season/week tuple.
    live = [row for row in rows if _as_utc(row.kickoff_at) <= current]
    selected = max(live, key=lambda row: _as_utc(row.kickoff_at)) if live else rows[0]
    return selected.season, selected.week


def run_iteration(*, now: datetime | None = None, client: ESPNClient | None = None) -> EspnCycleResult | None:
    if settings.scoring_mode not in {"shadow", "enabled"} or settings.scoring_provider.strip().lower() != "espn":
        raise RuntimeError("ESPN scoring worker requires SCORING_PROVIDER=espn and SCORING_MODE=shadow or enabled.")
    # This command is intentionally runnable without importing FastAPI.  Load
    # every relationship target before its first ORM query so a clean worker
    # process cannot appear healthy after logging a mapper-configuration error.
    ensure_models_registered()
    with SessionLocal() as db:
        window = resolve_scoring_window(db, now=now)
        if window is None:
            record_worker_heartbeat(
                db,
                worker_name="espn_scoring_processor",
                success=True,
                details={"state": "idle", "reason": "no_verified_schedule_window"},
            )
            db.commit()
            return None
        season, week = window
        created_client = client is None
        espn = client or ESPNClient()
        try:
            result = run_espn_scoring_cycle(
                db,
                season=season,
                week=week,
                mode=settings.scoring_mode,
                client=espn,
                worker_id="espn-scoring-scheduler",
                now=now,
            )
            # The admin report is also the durable alert-policy source.  Emit
            # structured worker logs only for actionable conditions; idle
            # no-game windows deliberately generate no alert noise.
            for alert in scoring_operations_report(db, season=season, week=week, now=now).get("alerts", []):
                severity = alert["severity"]
                logger.log(
                    logging.ERROR if severity in {"critical", "error"} else logging.WARNING,
                    "espn_scoring_alert severity=%s code=%s season=%s week=%s",
                    severity,
                    alert["code"],
                    season,
                    week,
                )
            record_worker_heartbeat(
                db,
                worker_name="espn_scoring_processor",
                success=result.failed_games == 0,
                details={
                    "mode": settings.scoring_mode,
                    "season": season,
                    "week": week,
                    "discovered_games": result.discovered_games,
                    "claimed_games": result.claimed_games,
                    "successful_games": result.successful_games,
                    "failed_games": result.failed_games,
                    "unmatched_rows": result.unmatched_rows,
                },
            )
            db.commit()
            return result
        finally:
            if created_client:
                espn.close()


def main() -> None:
    args = parse_args()
    if args.interval_seconds < 1:
        raise SystemExit("--interval-seconds must be at least one second")
    if settings.scoring_mode not in {"shadow", "enabled"} or settings.scoring_provider.strip().lower() != "espn":
        raise SystemExit("ESPN scoring worker requires SCORING_PROVIDER=espn and SCORING_MODE=shadow or enabled.")
    while True:
        started = time.monotonic()
        try:
            run_iteration()
        except Exception as error:  # pragma: no cover - operational failure path
            logger.exception("espn_scoring_iteration_failed", extra={"error": str(error)})
            if args.once:
                raise
        if args.once:
            return
        time.sleep(max(0, args.interval_seconds - (time.monotonic() - started)))


if __name__ == "__main__":
    main()
