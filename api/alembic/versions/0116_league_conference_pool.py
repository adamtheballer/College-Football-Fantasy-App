"""Persist the per-league conference player pool.

Revision ID: 0116_league_conference_pool
Revises: 0115_remove_punt_return_scoring
Create Date: 2026-09-19
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0116_league_conference_pool"
down_revision: str | None = "0115_remove_punt_return_scoring"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FULL_POOL_JSON = "'[\"SEC\", \"BIG10\", \"BIG12\", \"ACC\", \"INDEPENDENT\"]'"


def upgrade() -> None:
    op.add_column(
        "league_settings",
        sa.Column(
            "conference_codes",
            sa.JSON(),
            nullable=False,
            server_default=sa.text(_FULL_POOL_JSON),
        ),
    )
    op.alter_column("league_settings", "conference_codes", server_default=None)


def downgrade() -> None:
    op.drop_column("league_settings", "conference_codes")
