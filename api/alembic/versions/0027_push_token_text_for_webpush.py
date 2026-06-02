"""expand push token column for web push subscriptions

Revision ID: 0027_push_token_text_for_webpush
Revises: 0026_idempotency_requests
Create Date: 2026-05-27 16:20:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0027_push_token_text_for_webpush"
down_revision: str | None = "0026_idempotency_requests"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("push_tokens") as batch_op:
        batch_op.alter_column(
            "device_token",
            existing_type=sa.String(length=255),
            type_=sa.Text(),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("push_tokens") as batch_op:
        batch_op.alter_column(
            "device_token",
            existing_type=sa.Text(),
            type_=sa.String(length=255),
            existing_nullable=False,
        )
