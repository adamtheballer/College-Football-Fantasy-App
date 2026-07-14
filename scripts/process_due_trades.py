import argparse
import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.services.trade_service import process_trade_offers_once


def main() -> None:
    parser = argparse.ArgumentParser(description="Process accepted-pending trades that are due.")
    parser.parse_args()

    session = SessionLocal()
    try:
        result = process_trade_offers_once(session)
    finally:
        session.close()

    print(f"PROCESSED_DUE_TRADES: {result}")


if __name__ == "__main__":
    main()
