import argparse
import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.services.cfb27_player_sync import sync_cfb27_players


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync CFB27-rated fantasy players into the local player pool.")
    parser.add_argument("--dry-run", action="store_true", help="Report what would change without committing.")
    args = parser.parse_args()

    session = SessionLocal()
    try:
        result = sync_cfb27_players(session, dry_run=args.dry_run)
    finally:
        session.close()

    mode = "DRY RUN" if args.dry_run else "SYNCED"
    print(f"{mode}: {result}")


if __name__ == "__main__":
    main()
