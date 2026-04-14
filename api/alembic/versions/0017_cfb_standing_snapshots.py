"""add cfb standing snapshots

Revision ID: 0017_cfb_standing_snapshots
Revises: 0016_provider_sync_states
Create Date: 2026-04-05 13:40:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0017_cfb_standing_snapshots"
down_revision: str | None = "0016_provider_sync_states"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cfb_standing_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("team_name", sa.String(length=200), nullable=False),
        sa.Column("conference", sa.String(length=10), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("conference_rank", sa.Integer(), nullable=True),
        sa.Column("conference_wins", sa.Integer(), nullable=True),
        sa.Column("conference_losses", sa.Integer(), nullable=True),
        sa.Column("overall_wins", sa.Integer(), nullable=True),
        sa.Column("overall_losses", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="sportsdata"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "team_name",
            "conference",
            "season",
            name="uq_cfb_standing_snapshots_team_conf_season",
        ),
    )
    op.create_index(
        "ix_cfb_standing_snapshots_conf_season",
        "cfb_standing_snapshots",
        ["conference", "season"],
        unique=False,
    )
    op.create_index(
        "ix_cfb_standing_snapshots_season_rank",
        "cfb_standing_snapshots",
        ["season", "conference_rank"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_cfb_standing_snapshots_season_rank", table_name="cfb_standing_snapshots")
    op.drop_index("ix_cfb_standing_snapshots_conf_season", table_name="cfb_standing_snapshots")
    op.drop_table("cfb_standing_snapshots")
