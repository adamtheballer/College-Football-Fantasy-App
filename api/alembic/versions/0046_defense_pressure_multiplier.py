"""Persist the bounded pass-pressure adjustment used by weekly projections."""

from alembic import op
import sqlalchemy as sa


revision = "0046_defense_pressure_multiplier"
down_revision = "0045_player_role_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "defense_ratings",
        sa.Column("pass_pressure_multiplier", sa.Float(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("defense_ratings", "pass_pressure_multiplier")
