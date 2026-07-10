"""add team provider ids for roster lock readiness

Revision ID: 0047_team_provider_ids_lock_readiness
Revises: 0046_scoring_correction_affected_leagues
Create Date: 2026-07-10 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0047_team_provider_ids_lock_readiness"
down_revision: Union[str, None] = "0046_scoring_correction_affected_leagues"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "team_provider_ids",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("canonical_school", sa.String(length=200), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("provider_team_id", sa.String(length=120), nullable=False),
        sa.Column("provider_team_name", sa.String(length=200), nullable=True),
        sa.Column("provider_abbreviation", sa.String(length=50), nullable=True),
        sa.Column("match_confidence", sa.Integer(), server_default="100", nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["verified_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_team_id", name="uq_team_provider_ids_provider_team"),
        sa.UniqueConstraint("canonical_school", "provider", name="uq_team_provider_ids_school_provider"),
    )
    op.create_index("ix_team_provider_ids_school", "team_provider_ids", ["canonical_school"])
    op.create_index("ix_team_provider_ids_provider_team", "team_provider_ids", ["provider", "provider_team_id"])
    op.add_column("games", sa.Column("provider", sa.String(length=50), nullable=True))
    op.add_column("games", sa.Column("home_provider_team_id", sa.String(length=120), nullable=True))
    op.add_column("games", sa.Column("away_provider_team_id", sa.String(length=120), nullable=True))
    op.create_index("ix_games_provider_home_team", "games", ["provider", "home_provider_team_id"])
    op.create_index("ix_games_provider_away_team", "games", ["provider", "away_provider_team_id"])


def downgrade() -> None:
    op.drop_index("ix_games_provider_away_team", table_name="games")
    op.drop_index("ix_games_provider_home_team", table_name="games")
    op.drop_column("games", "away_provider_team_id")
    op.drop_column("games", "home_provider_team_id")
    op.drop_column("games", "provider")
    op.drop_index("ix_team_provider_ids_provider_team", table_name="team_provider_ids")
    op.drop_index("ix_team_provider_ids_school", table_name="team_provider_ids")
    op.drop_table("team_provider_ids")
