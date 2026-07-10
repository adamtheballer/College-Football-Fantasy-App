"""add affected league ids to scoring correction audits

Revision ID: 0046_scoring_correction_affected_leagues
Revises: 0045_provider_unmatched_resolution
Create Date: 2026-07-10 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0046_scoring_correction_affected_leagues"
down_revision: Union[str, None] = "0045_provider_unmatched_resolution"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "scoring_correction_audits",
        sa.Column("affected_league_ids", sa.JSON(), server_default=sa.text("'[]'::json"), nullable=False),
    )
    op.execute("UPDATE scoring_correction_audits SET affected_league_ids = json_build_array(league_id)")


def downgrade() -> None:
    op.drop_column("scoring_correction_audits", "affected_league_ids")
