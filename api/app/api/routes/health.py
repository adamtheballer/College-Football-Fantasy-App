from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.schemas.runtime import RuntimeDiagnosticsRead
from collegefootballfantasy_api.app.services.readiness import check_alembic_readiness

router = APIRouter()


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready", response_model=None)
def readiness_check(db: Session = Depends(get_db)):
    readiness = check_alembic_readiness(db).as_dict()
    if readiness["status"] != "ready":
        return JSONResponse(status_code=503, content=readiness)
    return readiness


@router.get("/health/runtime", response_model=RuntimeDiagnosticsRead)
def runtime_diagnostics(db: Session = Depends(get_db)):
    """Expose deployment identity and migration state without leaking secrets."""
    readiness = check_alembic_readiness(db).as_dict()
    payload = RuntimeDiagnosticsRead(
        status=str(readiness["status"]),
        environment=settings.environment,
        api_build_sha=settings.runtime_build_sha,
        database=str(readiness["database"]),
        migrations=str(readiness["migrations"]),
        expected_revisions=[str(revision) for revision in readiness["expected_revisions"]],
        current_revisions=[str(revision) for revision in readiness["current_revisions"]],
        detail=str(readiness["detail"]),
    )
    if payload.status != "ready":
        return JSONResponse(status_code=503, content=payload.model_dump())
    return payload
