"""Runtime provenance for release verification and stale-stack diagnosis."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.models.application_instance import ApplicationInstance
from collegefootballfantasy_api.app.schemas.runtime import DevelopmentRuntimeRead, RuntimeIdentityRead
from collegefootballfantasy_api.app.services.readiness import check_alembic_readiness


API_PROCESS_INSTANCE_UUID = str(uuid4())
API_STARTED_AT = datetime.now(timezone.utc)


def get_or_create_application_instance(db: Session, schema_version: str | None) -> ApplicationInstance:
    """Return the durable database identity without depending on seed data."""

    instance = db.get(ApplicationInstance, 1)
    if instance is not None:
        return instance

    instance = ApplicationInstance(
        id=1,
        instance_uuid=str(uuid4()),
        created_at=datetime.now(timezone.utc),
        environment=settings.environment,
        schema_version=schema_version,
    )
    db.add(instance)
    try:
        db.commit()
    except IntegrityError:
        # Another API process initialized the singleton first. Re-read the
        # durable row instead of treating ordinary concurrent startup as a 500.
        db.rollback()
        instance = db.get(ApplicationInstance, 1)
        if instance is None:  # pragma: no cover - protects database failures
            raise
    return instance


def build_public_runtime_identity(db: Session) -> RuntimeIdentityRead:
    readiness = check_alembic_readiness(db)
    try:
        instance = get_or_create_application_instance(db, ",".join(readiness.current_revisions))
    except SQLAlchemyError:
        db.rollback()
        instance = None
    return RuntimeIdentityRead(
        api_process_instance_uuid=API_PROCESS_INSTANCE_UUID,
        runtime_id=settings.runtime_id,
        runtime_mode=settings.runtime_mode,
        git_sha=settings.git_sha,
        git_branch=settings.git_branch,
        environment=settings.environment,
        database_instance_uuid=instance.instance_uuid if instance else None,
        alembic_version=readiness.current_revisions,
        readiness_status=readiness.status,
    )


def build_development_runtime(db: Session) -> DevelopmentRuntimeRead:
    identity = build_public_runtime_identity(db)
    return DevelopmentRuntimeRead(
        git_sha=identity.git_sha,
        git_branch=identity.git_branch,
        environment=identity.environment,
        runtime_mode=identity.runtime_mode,
        database_instance_uuid=identity.database_instance_uuid,
        alembic_revision=",".join(identity.alembic_version) or None,
        api_started_at=API_STARTED_AT,
    )
