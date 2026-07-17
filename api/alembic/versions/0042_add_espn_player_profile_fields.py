"""Persist ESPN player-profile enrichment fields.

Revision ID: 0042_espn_profile
Revises: 0041_score_compat
Create Date: 2026-07-17 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0042_espn_profile"
down_revision: str | None = "0041_score_compat"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("players") as batch:
        batch.add_column(sa.Column("espn_height", sa.String(length=40), nullable=True))
        batch.add_column(sa.Column("espn_weight", sa.String(length=40), nullable=True))
        batch.add_column(sa.Column("espn_birthplace", sa.String(length=300), nullable=True))
        batch.add_column(sa.Column("espn_status", sa.String(length=80), nullable=True))
        batch.add_column(sa.Column("espn_jersey", sa.String(length=20), nullable=True))
        batch.add_column(sa.Column("espn_headshot_url", sa.String(length=500), nullable=True))
        batch.add_column(sa.Column("espn_profile_synced_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("players") as batch:
        batch.drop_column("espn_profile_synced_at")
        batch.drop_column("espn_headshot_url")
        batch.drop_column("espn_jersey")
        batch.drop_column("espn_status")
        batch.drop_column("espn_birthplace")
        batch.drop_column("espn_weight")
        batch.drop_column("espn_height")
