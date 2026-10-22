"""product_activation

Revision ID: 0126_product_activation
Revises: 0125_challenge_experiences
Create Date: 2026-10-20 18:38:07.100388
"""
from alembic import op
import sqlalchemy as sa


revision = '0126_product_activation'
down_revision = '0125_challenge_experiences'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('product_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('dedupe_key', sa.String(length=180), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=32), nullable=False),
    sa.Column('challenge_id', sa.Integer(), nullable=True),
    sa.Column('at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('platform', sa.String(length=12), nullable=False),
    sa.Column('app_version', sa.String(length=40), nullable=True),
    sa.Column('app_build', sa.String(length=40), nullable=True),
    sa.ForeignKeyConstraint(['challenge_id'], ['weekly_challenges.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.CheckConstraint("kind IN ('session','challenge_view','challenge_start','challenge_submit','challenge_share','guide_complete','notification_open')", name='ck_product_events_kind'),
    sa.CheckConstraint("platform IN ('web','ios','android')", name='ck_product_events_platform'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('dedupe_key')
    )
    op.create_index('ix_product_events_at_kind', 'product_events', ['at', 'kind'], unique=False)
    op.create_index('ix_product_events_user_at', 'product_events', ['user_id', 'at'], unique=False)
    op.add_column('users', sa.Column('is_test_account', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('users', sa.Column('review_request_invoked_at', sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint('ck_users_review_invocation_claimed', 'users', 'review_request_invoked_at IS NULL OR review_request_claimed_at IS NOT NULL')
    # Confirmed automation account; do not guess test status from names/emails.
    op.execute("UPDATE users SET is_test_account = true WHERE username = 'adambajdechiautomation'")


def downgrade() -> None:
    op.drop_constraint('ck_users_review_invocation_claimed', 'users', type_='check')
    op.drop_column('users', 'review_request_invoked_at')
    op.drop_column('users', 'is_test_account')
    op.drop_index('ix_product_events_user_at', table_name='product_events')
    op.drop_index('ix_product_events_at_kind', table_name='product_events')
    op.drop_table('product_events')
