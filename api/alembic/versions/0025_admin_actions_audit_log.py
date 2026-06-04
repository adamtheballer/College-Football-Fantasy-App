"""add admin actions audit log table

Revision ID: 0025_admin_actions_audit_log
Revises: 0024_scheduled_league_jobs
Create Date: 2026-05-27 01:15:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0025_admin_actions_audit_log"
down_revision: str | None = "0024_scheduled_league_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "admin_actions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("action_type", sa.String(length=120), nullable=False),
        sa.Column("target_type", sa.String(length=120), nullable=False, server_default="league"),
        sa.Column("target_id", sa.Integer(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admin_actions_league_id_id", "admin_actions", ["league_id", "id"], unique=False)
    op.create_index("ix_admin_actions_league_action", "admin_actions", ["league_id", "action_type"], unique=False)
    op.create_index("ix_admin_actions_actor_user_id", "admin_actions", ["actor_user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_admin_actions_actor_user_id", table_name="admin_actions")
    op.drop_index("ix_admin_actions_league_action", table_name="admin_actions")
    op.drop_index("ix_admin_actions_league_id_id", table_name="admin_actions")
    op.drop_table("admin_actions")
