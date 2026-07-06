"""add scoring correction audit

Revision ID: 0025_scoring_correction_audit
Revises: 0024_provider_identity_audit
Create Date: 2026-07-06 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0025_scoring_correction_audit"
down_revision: Union[str, None] = "0024_provider_identity_audit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scoring_correction_audits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("source_stat_id", sa.Integer(), nullable=True),
        sa.Column("old_raw_json", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("new_raw_json", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("old_fantasy_points", sa.Float(), server_default="0", nullable=False),
        sa.Column("new_fantasy_points", sa.Float(), server_default="0", nullable=False),
        sa.Column("old_matchup_statuses", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("new_matchup_statuses", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_stat_id"], ["player_stats.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scoring_correction_audits_league_week", "scoring_correction_audits", ["league_id", "season", "week"])
    op.create_index("ix_scoring_correction_audits_player", "scoring_correction_audits", ["player_id"])


def downgrade() -> None:
    op.drop_index("ix_scoring_correction_audits_player", table_name="scoring_correction_audits")
    op.drop_index("ix_scoring_correction_audits_league_week", table_name="scoring_correction_audits")
    op.drop_table("scoring_correction_audits")
