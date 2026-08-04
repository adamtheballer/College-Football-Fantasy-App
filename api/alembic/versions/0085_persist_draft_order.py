"""persist draft order mode and commissioner positions

Revision ID: 0085_persist_draft_order
Revises: 0084_beta_access_schema
"""

from alembic import op
import sqlalchemy as sa


revision = "0085_persist_draft_order"
down_revision = "0084_beta_access_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "drafts",
        sa.Column("draft_order_mode", sa.String(length=20), nullable=False, server_default="random"),
    )
    op.add_column("teams", sa.Column("draft_position", sa.Integer(), nullable=True))
    op.create_index("ix_teams_league_draft_position", "teams", ["league_id", "draft_position"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_teams_league_draft_position", table_name="teams")
    op.drop_column("teams", "draft_position")
    op.drop_column("drafts", "draft_order_mode")
