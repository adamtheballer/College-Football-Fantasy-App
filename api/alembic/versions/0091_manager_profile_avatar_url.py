"""Add a public profile image URL for managers.

Revision ID: 0091_manager_profile_avatar_url
Revises: 0090_expand_league_icon_url
Create Date: 2026-08-19
"""

from alembic import op
import sqlalchemy as sa


revision = "0091_manager_profile_avatar_url"
down_revision = "0090_expand_league_icon_url"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("avatar_url", sa.String(length=2048), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("avatar_url")
