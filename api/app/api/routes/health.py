from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from api.app.db.session import get_db

router = APIRouter()


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
def readiness_check(db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "error",
                "database": "unavailable",
                "migrations": "unknown",
            },
        ) from exc
    try:
        migration_version = db.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "error",
                "database": "ok",
                "migrations": "missing",
            },
        ) from exc
    if not migration_version:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "error",
                "database": "ok",
                "migrations": "missing",
            },
        )
    return {
        "status": "ok",
        "database": "ok",
        "migrations": "ok",
        "alembic_version": str(migration_version),
    }
