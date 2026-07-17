#!/usr/bin/env python3
"""Create a worktree-local development .env without exposing secret values."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_ROOT / ".env"
ENV_EXAMPLE_FILE = PROJECT_ROOT / ".env.example"
ESPN_HISTORY_FLAG = "ESPN_HISTORICAL_STATS_ENABLED"
LEGACY_LOCAL_DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/collegefootballfantasy"
DEFAULT_LOCAL_DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5433/collegefootballfantasy"
PERSISTENT_LOCAL_DEFAULTS = {
    "COMPOSE_PROJECT_NAME": "cff_local",
    "DB_PORT": "5433",
    "API_PORT": "8000",
    "WEB_PORT": "8080",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare a local development .env file.")
    parser.add_argument(
        "--enable-espn-historical-stats",
        action="store_true",
        help="Allow the opt-in local ESPN historical importer in this worktree.",
    )
    return parser.parse_args()


def set_env_value(path: Path, key: str, value: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    replacement = f"{key}={value}"
    for index, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[index] = replacement
            break
    else:
        lines.append(replacement)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def migrate_legacy_local_database_url(path: Path) -> bool:
    """Move only the former stock local URL to the Compose-exposed PostgreSQL port."""

    lines = path.read_text(encoding="utf-8").splitlines()
    legacy_line = f"DATABASE_URL={LEGACY_LOCAL_DATABASE_URL}"
    for index, line in enumerate(lines):
        if line == legacy_line:
            lines[index] = f"DATABASE_URL={DEFAULT_LOCAL_DATABASE_URL}"
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return True
    return False


def ensure_missing_env_values(path: Path, values: dict[str, str]) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    existing_keys = {line.split("=", 1)[0] for line in lines if "=" in line and not line.lstrip().startswith("#")}
    added: list[str] = []
    for key, value in values.items():
        if key not in existing_keys:
            lines.append(f"{key}={value}")
            added.append(key)
    if added:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return added


def main() -> int:
    args = parse_args()
    if not ENV_FILE.exists():
        if not ENV_EXAMPLE_FILE.exists():
            raise FileNotFoundError(f"Missing local environment template: {ENV_EXAMPLE_FILE}")
        shutil.copyfile(ENV_EXAMPLE_FILE, ENV_FILE)
        print(f"Created worktree-local environment file: {ENV_FILE}")

    if migrate_legacy_local_database_url(ENV_FILE):
        print("Updated the former local DATABASE_URL default to port 5433 for the shared Docker database.")

    added_defaults = ensure_missing_env_values(ENV_FILE, PERSISTENT_LOCAL_DEFAULTS)
    if added_defaults:
        print(f"Added persistent local defaults: {', '.join(added_defaults)}.")

    if args.enable_espn_historical_stats:
        set_env_value(ENV_FILE, ESPN_HISTORY_FLAG, "true")
        print(f"Enabled {ESPN_HISTORY_FLAG} for this worktree.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
