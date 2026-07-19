"""Invalidate access tokens when account credentials change."""

from alembic import op
import sqlalchemy as sa


revision = "0051_auth_version"
down_revision = "0050_tx_processing_window"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("auth_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.execute(sa.text("UPDATE users SET auth_version = 1 WHERE auth_version IS NULL"))


def downgrade() -> None:
    op.drop_column("users", "auth_version")
