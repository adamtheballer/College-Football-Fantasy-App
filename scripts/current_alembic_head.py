#!/usr/bin/env python
"""Print the one canonical Alembic head used by CI and runtime gates."""
from __future__ import annotations

import sys

from collegefootballfantasy_api.app.services.readiness import get_canonical_alembic_head


def main() -> int:
    try:
        print(get_canonical_alembic_head())
    except ValueError as exc:
        print(f"Alembic head error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
