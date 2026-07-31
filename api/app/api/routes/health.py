from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.schemas.runtime import DevelopmentRuntimeRead, RuntimeIdentityRead
from collegefootballfantasy_api.app.services.readiness import check_alembic_readiness
from collegefootballfantasy_api.app.services.runtime_inspector import build_development_runtime, build_public_runtime_identity

router = APIRouter()


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/identity", response_model=RuntimeIdentityRead)
def runtime_identity(db: Session = Depends(get_db)) -> RuntimeIdentityRead:
    return build_public_runtime_identity(db)


@router.get("/health/runtime", response_model=DevelopmentRuntimeRead)
def development_runtime(db: Session = Depends(get_db)) -> DevelopmentRuntimeRead:
    if settings.environment.strip().lower() != "development":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    return build_development_runtime(db)


@router.get("/health/ready", response_model=None)
def readiness_check(db: Session = Depends(get_db)):
    readiness = check_alembic_readiness(db).as_dict()
    if readiness["status"] != "ready":
        return JSONResponse(status_code=503, content=readiness)
    return readiness
