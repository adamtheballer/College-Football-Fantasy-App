"""player week score status

Revision ID: 0026_player_week_score_status
Revises: 0025_waiver_claim_lifecycle
Create Date: 2026-07-11 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026_player_week_score_status"
down_revision: str | None = "0025_waiver_claim_lifecycle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "player_week_scores",
        sa.Column("status", sa.String(length=50), nullable=False, server_default="live"),
    )
    op.create_index("ix_player_week_scores_status", "player_week_scores", ["status"])


def downgrade() -> None:
    op.drop_index("ix_player_week_scores_status", table_name="player_week_scores")
    op.drop_column("player_week_scores", "status")
