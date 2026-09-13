"""Retire punt-return stats from CFFB scoring and public player data.

Revision ID: 0115_remove_punt_return_scoring
Revises: 0114_schedule_time_sync
Create Date: 2026-09-13
"""
from collections.abc import Sequence

from alembic import op
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.services.punt_return_policy_correction import (
    apply_punt_return_policy_correction,
)


revision: str = "0115_remove_punt_return_scoring"
down_revision: str | None = "0114_schedule_time_sync"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    session = Session(bind=op.get_bind())
    try:
        apply_punt_return_policy_correction(session)
        session.flush()
    finally:
        session.close()


def downgrade() -> None:
    # Retiring a scoring category is intentionally irreversible. Restoring a
    # source field cannot prove which historical fantasy totals used it.
    pass
