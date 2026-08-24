"""Allow shared Saturday Pick contests to outlive a deleted creator.

Revision ID: 0107_account_deletion_contest_creator
Revises: 0106_manager_name_cooldown
"""

import sqlalchemy as sa
from alembic import op


revision = "0107_account_deletion_contest_creator"
down_revision = "0106_manager_name_cooldown"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("saturday_pick_contests") as batch_op:
        batch_op.alter_column("created_by_user_id", existing_type=sa.Integer(), nullable=True)
        batch_op.drop_constraint("saturday_pick_contests_created_by_user_id_fkey", type_="foreignkey")
        batch_op.create_foreign_key(
            "saturday_pick_contests_created_by_user_id_fkey",
            "users",
            ["created_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("saturday_pick_contests") as batch_op:
        batch_op.drop_constraint("saturday_pick_contests_created_by_user_id_fkey", type_="foreignkey")
        batch_op.create_foreign_key(
            "saturday_pick_contests_created_by_user_id_fkey",
            "users",
            ["created_by_user_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.alter_column("created_by_user_id", existing_type=sa.Integer(), nullable=False)
