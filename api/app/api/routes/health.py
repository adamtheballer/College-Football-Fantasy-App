from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.db.session import get_db
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
