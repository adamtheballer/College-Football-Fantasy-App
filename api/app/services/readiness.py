from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.core.config import PROJECT_ROOT


DEFAULT_ALEMBIC_INI = PROJECT_ROOT / "api" / "alembic.ini"
DEFAULT_ALEMBIC_SCRIPT_LOCATION = PROJECT_ROOT / "api" / "alembic"


@dataclass(frozen=True)
class AlembicReadiness:
    status: str
    database: str
    migrations: str
    expected_revisions: list[str]
    current_revisions: list[str]
    detail: str

    @property
    def ready(self) -> bool:
        return self.status == "ready"

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "database": self.database,
            "migrations": self.migrations,
            "expected_revisions": self.expected_revisions,
            "current_revisions": self.current_revisions,
            "detail": self.detail,
        }


def get_alembic_heads(alembic_ini_path: Path | str = DEFAULT_ALEMBIC_INI) -> list[str]:
    config = Config(str(alembic_ini_path))
    config.set_main_option("script_location", str(DEFAULT_ALEMBIC_SCRIPT_LOCATION))
    script = ScriptDirectory.from_config(config)
    return sorted(script.get_heads())


def check_alembic_readiness(
    db: Session,
    *,
    alembic_ini_path: Path | str = DEFAULT_ALEMBIC_INI,
) -> AlembicReadiness:
    expected_revisions = get_alembic_heads(alembic_ini_path)
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return AlembicReadiness(
            status="not_ready",
            database="unreachable",
            migrations="unknown",
            expected_revisions=expected_revisions,
            current_revisions=[],
            detail="database connection failed",
        )

    try:
        rows = db.execute(text("SELECT version_num FROM alembic_version")).all()
    except SQLAlchemyError:
        return AlembicReadiness(
            status="not_ready",
            database="ready",
            migrations="missing",
            expected_revisions=expected_revisions,
            current_revisions=[],
            detail="alembic_version table is missing",
        )

    current_revisions = sorted(str(row[0]) for row in rows if row[0])
    if not current_revisions:
        return AlembicReadiness(
            status="not_ready",
            database="ready",
            migrations="missing",
            expected_revisions=expected_revisions,
            current_revisions=[],
            detail="alembic_version table has no revision rows",
        )

    if current_revisions != expected_revisions:
        return AlembicReadiness(
            status="not_ready",
            database="ready",
            migrations="out_of_date",
            expected_revisions=expected_revisions,
            current_revisions=current_revisions,
            detail="database migration revision does not match repository head",
        )

    return AlembicReadiness(
        status="ready",
        database="ready",
        migrations="ready",
        expected_revisions=expected_revisions,
        current_revisions=current_revisions,
        detail="database is reachable and migrations are at repository head",
    )
