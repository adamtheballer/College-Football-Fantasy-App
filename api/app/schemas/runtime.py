from datetime import datetime

from pydantic import BaseModel


class RuntimeIdentityRead(BaseModel):
    """Safe deployment provenance exposed by every environment."""

    api_process_instance_uuid: str
    runtime_id: str | None = None
    git_sha: str
    git_branch: str
    environment: str
    database_instance_uuid: str | None = None
    alembic_version: list[str]
    readiness_status: str


class DevelopmentRuntimeRead(BaseModel):
    """Development-only diagnostics; never expose connection details."""

    git_sha: str
    git_branch: str
    environment: str
    database_instance_uuid: str | None = None
    alembic_revision: str | None = None
    api_started_at: datetime
