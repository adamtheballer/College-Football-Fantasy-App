"""Allow standard public image URLs for league icons.

Revision ID: 0090_expand_league_icon_url
Revises: 0089_trade_private_chat
Create Date: 2026-08-10
"""

from alembic import op
import sqlalchemy as sa


revision = "0090_expand_league_icon_url"
down_revision = "0089_trade_private_chat"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("leagues") as batch_op:
        batch_op.alter_column(
            "icon_url",
            existing_type=sa.String(length=500),
            type_=sa.String(length=2048),
            existing_nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("leagues") as batch_op:
        batch_op.alter_column(
            "icon_url",
            existing_type=sa.String(length=2048),
            type_=sa.String(length=500),
            existing_nullable=True,
        )
