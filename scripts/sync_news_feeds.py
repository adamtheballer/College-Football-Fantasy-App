import argparse

from api.app.db.session import SessionLocal
from api.app.services.news_ingestion import run_news_ingestion


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync fantasy-relevant college football news feeds.")
    parser.add_argument("--source", choices=["all", "cfn"], default="all")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    db = SessionLocal()
    try:
        result = run_news_ingestion(
            db,
            source_slug=args.source,
            limit=args.limit,
            force=args.force,
            dry_run=args.dry_run,
        )
        print(f"sources checked: {result.sources_checked}")
        print(f"entries found: {result.rows_seen}")
        print(f"inserted: {result.rows_inserted}")
        print(f"updated: {result.rows_updated}")
        print(f"duplicates skipped: {result.duplicates_skipped}")
        print(f"low relevance skipped: {result.low_relevance_skipped}")
        print(f"errors: {result.errors}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
