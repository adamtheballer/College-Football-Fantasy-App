from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.schemas.runtime import RuntimeIdentityRead
from collegefootballfantasy_api.app.services.readiness import check_alembic_readiness
from collegefootballfantasy_api.app.services.runtime_inspector import build_public_runtime_identity

router = APIRouter()


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/identity", response_model=RuntimeIdentityRead)
def runtime_identity(db: Session = Depends(get_db)) -> RuntimeIdentityRead:
    return build_public_runtime_identity(db)


@router.get("/health/runtime", response_model=RuntimeIdentityRead)
def runtime_identity_for_browser(db: Session = Depends(get_db)) -> RuntimeIdentityRead:
    """Public, non-secret runtime compatibility contract for every environment."""
    return build_public_runtime_identity(db)


@router.get("/health/ready", response_model=None)
def readiness_check(db: Session = Depends(get_db)):
    readiness = check_alembic_readiness(db).as_dict()
    if readiness["status"] != "ready":
        return JSONResponse(status_code=503, content=readiness)
    return readiness
