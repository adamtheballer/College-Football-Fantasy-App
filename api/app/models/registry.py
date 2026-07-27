"""Backward-compatible entry point for standalone model registration.

``app.db.model_registry`` is the single maintained registry used by FastAPI,
Alembic, and release scripts. Keep this historical import path as a small
delegate so legacy scripts cannot silently run with an incomplete model set.
"""

from collegefootballfantasy_api.app.db.model_registry import ensure_models_registered


def load_all_models() -> None:
    ensure_models_registered()
