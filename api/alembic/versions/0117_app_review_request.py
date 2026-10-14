"""Persist lifetime iOS automatic review authorization on the account.

Revision ID: 0117_app_review_request
Revises: 0116_league_conference_pool
"""
from alembic import op
import sqlalchemy as sa

revision = "0117_app_review_request"
down_revision = "0116_league_conference_pool"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing accounts start unconsumed. No historical review activity inferred.
    op.add_column("users", sa.Column("review_request_claimed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("review_request_app_version", sa.String(80), nullable=True))
    op.add_column("users", sa.Column("review_request_app_build", sa.String(80), nullable=True))
    op.create_check_constraint("ck_users_review_request_metadata", "users",
        "(review_request_claimed_at IS NULL AND review_request_app_version IS NULL AND review_request_app_build IS NULL) OR "
        "(review_request_claimed_at IS NOT NULL AND review_request_app_version IS NOT NULL AND review_request_app_build IS NOT NULL)")


def downgrade() -> None:
    # Never erase lifetime consumption during an application rollback.
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM users WHERE review_request_claimed_at IS NOT NULL)")):
        raise RuntimeError("Cannot remove the review ledger after claims; disable IOS_APP_REVIEW_ENABLED and roll back application code only.")
    op.drop_constraint("ck_users_review_request_metadata", "users", type_="check")
    op.drop_column("users", "review_request_app_build")
    op.drop_column("users", "review_request_app_version")
    op.drop_column("users", "review_request_claimed_at")
