from pydantic import BaseModel


class RuntimeIdentityRead(BaseModel):
    """Safe deployment provenance exposed by every environment."""

    api_process_instance_uuid: str
    runtime_id: str | None = None
    runtime_mode: str
    git_sha: str
    git_branch: str
    web_git_sha: str
    worker_git_sha: str
    environment: str
    email_enabled: bool
    password_reset_enabled: bool
    password_reset_email_configured: bool
    support_email: str | None = None
    privacy_policy_url: str | None = None
    terms_url: str | None = None
    provider_disclosure_url: str | None = None
    scoring_mode: str
    sportsdata_enabled: bool
    scoring_worker_expected: bool
    provider_polling_expected: bool
    player_dataset_version: str
    projection_dataset_version: str
    cfb27_rating_dataset_version: str
    database_instance_uuid: str | None = None
    alembic_version: list[str]
    alembic_revision: str | None = None
    readiness_status: str
