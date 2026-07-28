from __future__ import annotations

from pydantic import BaseModel


class RuntimeDiagnosticsRead(BaseModel):
    """Public, non-secret identity information for diagnosing artifact mismatches."""

    status: str
    environment: str
    api_build_sha: str
    database: str
    migrations: str
    expected_revisions: list[str]
    current_revisions: list[str]
    detail: str
