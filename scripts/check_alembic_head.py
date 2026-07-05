#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.services.readiness import (
    DEFAULT_ALEMBIC_INI,
    check_alembic_readiness,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify database Alembic revision matches repository head.")
    parser.add_argument(
        "--database-url",
        default=settings.database_url,
        help="SQLAlchemy database URL. Defaults to DATABASE_URL/settings.database_url.",
    )
    parser.add_argument(
        "--alembic-ini",
        default=str(DEFAULT_ALEMBIC_INI),
        help="Path to api/alembic.ini.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    engine = create_engine(args.database_url, pool_pre_ping=True)
    with Session(engine) as db:
        readiness = check_alembic_readiness(db, alembic_ini_path=Path(args.alembic_ini))

    payload = readiness.as_dict()
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if readiness.ready else 1


if __name__ == "__main__":
    sys.exit(main())
