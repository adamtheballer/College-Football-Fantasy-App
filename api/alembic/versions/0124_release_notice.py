"""release notice

Revision ID: 0124_release_notice
Revises: 0123_weekly_challenges
Create Date: 2026-10-15 18:06:02.511792
"""
from alembic import op
import sqlalchemy as sa


revision = '0124_release_notice'
down_revision = '0123_weekly_challenges'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Additive account/release receipt; no existing user is pre-consumed.
    op.create_table('user_release_notices',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('release_key', sa.String(length=40), nullable=False),
    sa.Column('claimed_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'release_key')
    )


def downgrade() -> None:
    if op.get_bind().execute(sa.text("SELECT EXISTS (SELECT 1 FROM user_release_notices)")).scalar():
        raise RuntimeError("Release notice receipts exist; retain the schema to preserve once-per-account history.")
    op.drop_table('user_release_notices')
