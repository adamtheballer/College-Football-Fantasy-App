"""Quarantine legacy weekly projection rows that predate the beta input audit.

Revision ID: 0062_quarantine_legacy_proj
Revises: 0061_reconcile_player_bio
"""

import sqlalchemy as sa
from alembic import op


revision = "0062_quarantine_legacy_proj"
down_revision = "0061_reconcile_player_bio"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "weekly_projections",
        "model_version",
        server_default="v3_beta_weighted",
    )
    op.execute(
        sa.text(
            """
            UPDATE weekly_projections
            SET model_version = 'legacy_unverified',
                projection_status = 'UNVERIFIED',
                fallback_reason = COALESCE(fallback_reason, 'generated before beta input audit')
            WHERE team_id IS NULL
            """
        )
    )


def downgrade() -> None:
    # Legacy rows cannot be promoted safely without their missing input audit.
    pass
