#!/usr/bin/env python
"""Exercise the canonical playoff migration on disposable PostgreSQL databases.

This script is intentionally a CI-only certification: it creates two random
databases next to the supplied disposable PostgreSQL database and drops both
on completion. It never accepts a production URL.
"""
from __future__ import annotations

import os
import secrets
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.services.readiness import get_canonical_alembic_head


ROOT = Path(__file__).resolve().parents[1]
LEGACY_REVISION = "0101_injury_notification_scope"


def _require_disposable_postgres(url: URL) -> None:
    if not url.drivername.startswith("postgresql"):
        raise SystemExit("postseason migration certification requires PostgreSQL")
    environment = os.getenv("ENVIRONMENT", "").lower()
    if environment in {"production", "staging"}:
        raise SystemExit("refusing to create certification databases outside a disposable environment")


def _run_alembic(database_url: str, *arguments: str) -> str:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    environment["PYTHONPATH"] = str(ROOT)
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "api/alembic.ini", *arguments],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(
            f"alembic {' '.join(arguments)} failed:\n{result.stdout}\n{result.stderr}"
        )
    return result.stdout


@contextmanager
def _temporary_database(base_url: URL):
    database_name = f"cff_postseason_cert_{secrets.token_hex(6)}"
    admin_url = base_url.set(database="postgres")
    target_url = base_url.set(database=database_name)
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{database_name}"'))
        yield target_url.render_as_string(hide_password=False)
    finally:
        with admin_engine.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)'))
        admin_engine.dispose()


def _constraint_names(connection, table: str) -> set[str]:
    return set(
        connection.execute(
            text(
                "SELECT conname FROM pg_constraint "
                "WHERE conrelid = CAST(:table_name AS regclass)"
            ),
            {"table_name": table},
        ).scalars()
    )


def _index_names(connection, table: str) -> set[str]:
    return set(
        connection.execute(
            text("SELECT indexname FROM pg_indexes WHERE schemaname = 'public' AND tablename = :table_name"),
            {"table_name": table},
        ).scalars()
    )


def _seed_legacy_postseason_rows(database_url: str) -> None:
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO leagues "
                    "(id, name, platform, scoring_type, season_year, max_teams, is_private, status) "
                    "VALUES (1, 'Migration League', 'custom', 'espn_full_ppr', 2026, 4, true, 'pre_draft'), "
                    "(2, 'Unlinked Legacy League', 'custom', 'espn_full_ppr', 2026, 4, true, 'pre_draft')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO teams (id, league_id, name, owner_name, draft_position) VALUES "
                    "(1, 1, 'Team One', 'One', 1), (2, 1, 'Team Two', 'Two', 2), "
                    "(3, 2, 'Legacy Team', 'Three', 1)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO postseason_brackets "
                    "(id, league_id, season, bracket_type, status, total_teams, total_rounds) "
                    "VALUES (1, 1, 2026, 'CHAMPIONSHIP', 'COMPLETED', 2, 1)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO postseason_final_standings "
                    "(id, league_id, season, team_id, final_place, regular_season_rank, playoff_seed, "
                    "postseason_result, wins, losses, ties, points_for, finalized_at) VALUES "
                    "(1, 1, 2026, 1, 1, 1, 1, 'CHAMPION', 10, 2, 0, 1500, now()), "
                    "(2, 1, 2026, 2, 2, 2, 2, 'RUNNER_UP', 9, 3, 0, 1450, now()), "
                    "(3, 2, 2026, 3, 1, 1, NULL, 'LEGACY', 8, 4, 0, 1300, now())"
                )
            )
    finally:
        engine.dispose()


def _assert_post_0102_schema(database_url: str) -> None:
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            linked = connection.execute(
                text("SELECT id, bracket_id FROM postseason_final_standings ORDER BY id")
            ).all()
            assert linked == [(1, 1), (2, 1), (3, None)]

            # A permanent league retains one bracket per season, not one for
            # its lifetime; this is the intended 2026/2027 history contract.
            connection.execute(
                text(
                    "INSERT INTO postseason_brackets "
                    "(id, league_id, season, bracket_type, status, total_teams, total_rounds) "
                    "VALUES (2, 1, 2027, 'CHAMPIONSHIP', 'PLANNED', 4, 2) "
                    "ON CONFLICT DO NOTHING"
                )
            )
            bracket_seasons = connection.execute(
                text("SELECT season FROM postseason_brackets WHERE league_id = 1 ORDER BY season")
            ).scalars().all()
            assert bracket_seasons == [2026, 2027]

            assert {
                "ix_postseason_matchups_fantasy_matchup",
            } <= _index_names(connection, "postseason_matchups")
            bracket_columns = set(
                connection.execute(
                    text("SELECT column_name FROM information_schema.columns WHERE table_name = 'postseason_brackets'")
                ).scalars()
            )
            settings_columns = set(
                connection.execute(
                    text("SELECT column_name FROM information_schema.columns WHERE table_name = 'league_postseason_settings'")
                ).scalars()
            )
            assert {
                "championship_week", "calendar_policy_version", "calendar_source_identity",
                "calendar_source_revision", "calendar_source_sha256", "calendar_source_format_version",
            } <= bracket_columns
            assert {
                "calendar_policy_version", "calendar_source_identity", "calendar_source_revision",
                "calendar_source_sha256", "calendar_source_format_version",
            } <= settings_columns
            assert {
                "ix_postseason_final_standings_bracket",
            } <= _index_names(connection, "postseason_final_standings")
            assert {
                # Retained for unlinked legacy rows (where nullable bracket_id
                # would otherwise not provide uniqueness on PostgreSQL).
                "uq_postseason_final_standing_team",
                "uq_postseason_final_standing_place",
                "uq_postseason_final_standing_bracket_team",
                "uq_postseason_final_standing_bracket_place",
            } <= _constraint_names(connection, "postseason_final_standings")
    finally:
        engine.dispose()


def certify() -> None:
    base_url = make_url(settings.database_url)
    _require_disposable_postgres(base_url)
    canonical_head = get_canonical_alembic_head()

    # A. Empty PostgreSQL must reach the sole repository head and have no
    # metadata drift.
    with _temporary_database(base_url) as fresh_url:
        _run_alembic(fresh_url, "upgrade", "head")
        _run_alembic(fresh_url, "check")
        engine = create_engine(fresh_url)
        try:
            with engine.connect() as connection:
                assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == canonical_head
        finally:
            engine.dispose()

    # B/C. Upgrade real legacy rows, then prove the operation reverses and
    # re-applies without losing the old standings data.
    with _temporary_database(base_url) as legacy_url:
        _run_alembic(legacy_url, "upgrade", LEGACY_REVISION)
        _seed_legacy_postseason_rows(legacy_url)
        _run_alembic(legacy_url, "upgrade", "head")
        _run_alembic(legacy_url, "check")
        _assert_post_0102_schema(legacy_url)
        _run_alembic(legacy_url, "downgrade", LEGACY_REVISION)
        _run_alembic(legacy_url, "upgrade", "head")
        _run_alembic(legacy_url, "check")
        _assert_post_0102_schema(legacy_url)


if __name__ == "__main__":
    certify()
    print("Postseason PostgreSQL migration certification passed")
