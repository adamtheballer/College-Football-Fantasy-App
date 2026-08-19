"""Allow compact manager photo data URLs.

Revision ID: 0098_profile_photo_data
Revises: 0097_merge_avatar_live_heads
Create Date: 2026-08-19
"""

from alembic import op
import sqlalchemy as sa


revision = "0098_profile_photo_data"
down_revision = "0097_merge_avatar_live_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("avatar_url", existing_type=sa.String(length=2048), type_=sa.Text(), existing_nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("avatar_url", existing_type=sa.Text(), type_=sa.String(length=2048), existing_nullable=True)
