#!/usr/bin/env python
"""Certify alpha migrations and durable worker boot on disposable PostgreSQL.

This script is intentionally CI-only.  It refuses non-PostgreSQL and named
production/staging environments, reuses the existing migration compatibility
exercise for fresh/legacy/reversal coverage, then proves the actual worker
entry points can register healthy heartbeats against the migrated database.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from collegefootballfantasy_api.app.core.config import settings
from scripts.certify_postseason_migrations import certify as certify_migrations


ROOT = Path(__file__).resolve().parents[1]
WORKERS = (
    ("lifecycle_processor", "scripts/run_lifecycle_worker.py"),
    ("notification_processor", "scripts/run_notification_worker.py"),
    ("espn_scoring_processor", "scripts/run_espn_scoring_worker.py"),
)


def _require_disposable_postgres() -> None:
    database_url = make_url(settings.database_url)
    if not database_url.drivername.startswith("postgresql"):
        raise SystemExit("alpha PostgreSQL rehearsal requires a PostgreSQL database")
    if os.getenv("ENVIRONMENT", "").lower() in {"production", "staging"}:
        raise SystemExit("alpha PostgreSQL rehearsal refuses production or staging")
    if os.getenv("CFF_ALPHA_DISPOSABLE_CERTIFICATION") != "1":
        raise SystemExit("set CFF_ALPHA_DISPOSABLE_CERTIFICATION=1 for the disposable CI rehearsal")


def _run_worker(script: str) -> None:
    result = subprocess.run(
        [sys.executable, script, "--once"],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(f"{script} --once failed:\n{result.stdout}\n{result.stderr}")


def certify() -> None:
    _require_disposable_postgres()
    certify_migrations()

    for _worker_name, script in WORKERS:
        _run_worker(script)

    engine = create_engine(settings.database_url)
    try:
        with engine.connect() as connection:
            healthy_workers = set(
                connection.execute(
                    text(
                        "SELECT worker_name FROM worker_heartbeats "
                        "WHERE worker_name = ANY(:worker_names) AND status = 'healthy'"
                    ),
                    {"worker_names": [worker_name for worker_name, _script in WORKERS]},
                ).scalars()
            )
    finally:
        engine.dispose()

    expected_workers = {worker_name for worker_name, _script in WORKERS}
    if healthy_workers != expected_workers:
        raise RuntimeError(f"worker boot rehearsal failed: expected {expected_workers}, got {healthy_workers}")


if __name__ == "__main__":
    certify()
    print("Alpha PostgreSQL migration and worker boot rehearsal passed")
