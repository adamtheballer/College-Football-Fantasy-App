from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.models.scoring_run import ScoringRun


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check latest scoring worker run health.")
    parser.add_argument("--provider", default="espn")
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--league-id", type=int, default=None)
    parser.add_argument("--max-age-seconds", type=int, default=180)
    return parser.parse_args()


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def main() -> int:
    args = parse_args()
    with SessionLocal() as db:
        query = db.query(ScoringRun).filter(
            ScoringRun.provider == args.provider,
            ScoringRun.season == args.season,
            ScoringRun.week == args.week,
        )
        if args.league_id is None:
            query = query.filter(ScoringRun.league_id.is_(None))
        else:
            query = query.filter(ScoringRun.league_id == args.league_id)
        run = query.order_by(ScoringRun.started_at.desc(), ScoringRun.id.desc()).first()

    if not run:
        print("CRITICAL no scoring run found")
        return 2
    if run.status == "running":
        print(f"WARNING scoring run still running run_id={run.id} started_at={run.started_at}")
        return 1
    if run.status != "success":
        print(f"CRITICAL latest scoring run failed run_id={run.id} status={run.status} error={run.error_message}")
        return 2
    completed_at = run.completed_at or run.started_at
    age_seconds = int((datetime.now(timezone.utc) - _aware(completed_at)).total_seconds())
    if age_seconds > args.max_age_seconds:
        print(f"WARNING scoring run stale run_id={run.id} age_seconds={age_seconds}")
        return 1
    print(
        f"OK run_id={run.id} age_seconds={age_seconds} rows_fetched={run.rows_fetched} "
        f"rows_matched={run.rows_matched} rows_unmatched={run.rows_unmatched} retry_count={run.retry_count}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
