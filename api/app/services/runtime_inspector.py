"""Runtime provenance for release verification and stale-stack diagnosis."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.models.application_instance import ApplicationInstance
from collegefootballfantasy_api.app.schemas.runtime import RuntimeIdentityRead
from collegefootballfantasy_api.app.services.readiness import check_alembic_readiness


API_PROCESS_INSTANCE_UUID = str(uuid4())


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
        web_git_sha=settings.web_git_sha,
        worker_git_sha=settings.worker_git_sha,
        environment=settings.environment,
        email_enabled=settings.email_enabled,
        password_reset_enabled=settings.password_reset_enabled,
        password_reset_email_configured=settings.password_reset_enabled and settings.email_enabled,
        support_email=settings.support_email,
        privacy_policy_url=settings.privacy_policy_url,
        terms_url=settings.terms_url,
        provider_disclosure_url=settings.provider_disclosure_url,
        scoring_mode=settings.scoring_mode,
        sportsdata_enabled=settings.sportsdata_enabled,
        scoring_worker_expected=settings.scoring_worker_expected,
        provider_polling_expected=settings.provider_polling_expected,
        player_dataset_version=settings.player_dataset_version,
        projection_dataset_version=settings.projection_dataset_version,
        cfb27_rating_dataset_version=settings.cfb27_rating_dataset_version,
        database_instance_uuid=instance.instance_uuid if instance else None,
        alembic_version=readiness.current_revisions,
        alembic_revision=",".join(readiness.current_revisions) or None,
        readiness_status=readiness.status,
    )
