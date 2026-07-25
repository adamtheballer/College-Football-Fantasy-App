"""persist projection stat-profile metadata and kicker stat lines

Revision ID: 0058_projection_stat_profiles
Revises: 0057_player_season_ranks
Create Date: 2026-07-24 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0058_projection_stat_profiles"
down_revision: str | None = "0057_player_season_ranks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "weekly_projections",
        sa.Column("field_goals_made_0_to_49", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "weekly_projections",
        sa.Column("field_goals_made_50_plus", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "weekly_projections",
        sa.Column("extra_points_made", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "weekly_projections",
        sa.Column("neutral_baseline", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "weekly_projections",
        sa.Column("baseline_games_played", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "weekly_projections",
        sa.Column("baseline_source", sa.String(length=40), nullable=False, server_default="position_default"),
    )


def downgrade() -> None:
    op.drop_column("weekly_projections", "baseline_source")
    op.drop_column("weekly_projections", "baseline_games_played")
    op.drop_column("weekly_projections", "neutral_baseline")
    op.drop_column("weekly_projections", "extra_points_made")
    op.drop_column("weekly_projections", "field_goals_made_50_plus")
    op.drop_column("weekly_projections", "field_goals_made_0_to_49")
