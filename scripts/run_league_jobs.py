import argparse
import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.services.job_queue import run_due_jobs_for_league


def main() -> None:
    parser = argparse.ArgumentParser(description="Run due scheduled league jobs.")
    parser.add_argument("--league-id", type=int, default=None)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--worker-id", type=str, default="script:run_league_jobs")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    session = SessionLocal()
    try:
        if args.league_id is not None:
            league_ids = [args.league_id]
        else:
            league_ids = [row[0] for row in session.query(League.id).all()]

        for league_id in league_ids:
            result = run_due_jobs_for_league(
                session,
                league_id=int(league_id),
                worker_id=args.worker_id,
                limit=args.limit,
            )
            if result.processed:
                print(
                    f"league={league_id} processed={result.processed} completed={result.completed} failed={result.failed}"
                )
            for row in result.results:
                print(f"  job={row.job_id} type={row.job_type} status={row.status} detail={row.detail}")

        if args.dry_run:
            session.rollback()
        else:
            session.commit()
    finally:
        session.close()


if __name__ == "__main__":
    main()
