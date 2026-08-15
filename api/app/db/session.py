from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from collegefootballfantasy_api.app.core.config import settings


def normalize_database_url(database_url: str) -> str:
    """Use the installed psycopg v3 SQLAlchemy dialect for generic Postgres URLs."""

    if database_url.startswith("postgresql://"):
        return f"postgresql+psycopg://{database_url.removeprefix('postgresql://')}"
    if database_url.startswith("postgres://"):
        return f"postgresql+psycopg://{database_url.removeprefix('postgres://')}"
    return database_url


engine = create_engine(normalize_database_url(settings.database_url), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
