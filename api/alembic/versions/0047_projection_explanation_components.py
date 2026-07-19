"""Persist numeric projection component explanations."""

from alembic import op
import sqlalchemy as sa


revision = "0047_projection_components"
down_revision = "0046_defense_pressure_multiplier"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projection_explanations", sa.Column("components", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("projection_explanations", "components")
