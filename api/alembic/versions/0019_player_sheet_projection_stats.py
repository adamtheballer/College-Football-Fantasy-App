"""add sheet projection stats json on players

Revision ID: 0019_sheet_proj_stats
Revises: 0018_sheet_projection_fields
Create Date: 2026-05-26 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0019_sheet_proj_stats"
down_revision: str | None = "0018_sheet_projection_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("players", sa.Column("sheet_projection_stats", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("players", "sheet_projection_stats")
