"""Store projected 0--39 and 40--49 field goals separately.

Revision ID: 0067_split_projection_fg
Revises: 0066_event_effective_timestamps
"""

from alembic import op
import sqlalchemy as sa


revision = "0067_split_projection_fg"
down_revision = "0066_event_effective_timestamps"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "weekly_projections",
        sa.Column("field_goals_made_0_to_39", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "weekly_projections",
        sa.Column("field_goals_made_40_to_49", sa.Float(), nullable=False, server_default="0"),
    )
    # Existing rows only contain their original 0--49 aggregate. Retain it in
    # the compatible 0--39 bucket; new generation writes the exact split.
    op.execute(
        "UPDATE weekly_projections SET field_goals_made_0_to_39 = field_goals_made_0_to_49 "
        "WHERE field_goals_made_0_to_49 IS NOT NULL"
    )
    op.alter_column("weekly_projections", "field_goals_made_0_to_39", server_default=None)
    op.alter_column("weekly_projections", "field_goals_made_40_to_49", server_default=None)


def downgrade() -> None:
    op.drop_column("weekly_projections", "field_goals_made_40_to_49")
    op.drop_column("weekly_projections", "field_goals_made_0_to_39")
