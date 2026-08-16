#!/usr/bin/env python3
"""Dry-run or apply the approved legacy beta kicker scoring correction."""

from __future__ import annotations

import argparse
import json

from collegefootballfantasy_api.app.db.model_registry import ensure_models_registered
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.services.legacy_kicker_migration import (
    apply_legacy_kicker_migration,
    render_migration_plan,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", required=True, type=int)
    parser.add_argument("--apply", action="store_true", help="Apply the proven eligible plans. Default is dry-run.")
    args = parser.parse_args()
    ensure_models_registered()
    with SessionLocal() as db:
        if not args.apply:
            print(json.dumps(render_migration_plan(db, season=args.season), indent=2, sort_keys=True, default=str))
            return
        try:
            result = apply_legacy_kicker_migration(db, season=args.season)
            db.commit()
        except Exception:
            db.rollback()
            raise
        print(json.dumps(result, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
