"""player image urls

Revision ID: 0009_player_image_urls
Revises: 0008_team_stats
Create Date: 2026-03-21 01:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0009_player_image_urls"
down_revision = "0008_team_stats"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("players", sa.Column("image_url", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("players", "image_url")
