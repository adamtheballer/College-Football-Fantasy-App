"""add idempotency requests table

Revision ID: 0026_idempotency_requests
Revises: 0025_admin_actions_audit_log
Create Date: 2026-05-27 06:50:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0026_idempotency_requests"
down_revision: str | None = "0025_admin_actions_audit_log"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "idempotency_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scope", sa.String(length=180), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="in_progress"),
        sa.Column("response_status_code", sa.Integer(), nullable=True),
        sa.Column("response_payload", sa.JSON(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scope", "idempotency_key", name="uq_idempotency_requests_scope_key"),
    )
    op.create_index(
        "ix_idempotency_requests_scope_status",
        "idempotency_requests",
        ["scope", "status"],
        unique=False,
    )
    op.create_index(
        "ix_idempotency_requests_user",
        "idempotency_requests",
        ["created_by_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_idempotency_requests_user", table_name="idempotency_requests")
    op.drop_index("ix_idempotency_requests_scope_status", table_name="idempotency_requests")
    op.drop_table("idempotency_requests")
