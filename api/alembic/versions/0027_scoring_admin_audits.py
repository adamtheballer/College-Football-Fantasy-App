"""scoring admin audits

Revision ID: 0027_scoring_admin_audits
Revises: 0026_player_week_score_status
Create Date: 2026-07-11 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0027_scoring_admin_audits"
down_revision: str | None = "0026_player_week_score_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scoring_admin_audits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("league_id", sa.Integer(), nullable=True),
        sa.Column("season", sa.Integer(), nullable=True),
        sa.Column("week", sa.Integer(), nullable=True),
        sa.Column("player_id", sa.Integer(), nullable=True),
        sa.Column("affected_league_ids", sa.JSON(), nullable=True),
        sa.Column("reason", sa.String(length=1000), nullable=False),
        sa.Column("before_state", sa.JSON(), nullable=True),
        sa.Column("after_state", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scoring_admin_audits_action", "scoring_admin_audits", ["action"])
    op.create_index("ix_scoring_admin_audits_actor_user_id", "scoring_admin_audits", ["actor_user_id"])
    op.create_index("ix_scoring_admin_audits_league_week", "scoring_admin_audits", ["league_id", "season", "week"])
    op.create_index("ix_scoring_admin_audits_player_week", "scoring_admin_audits", ["player_id", "season", "week"])


def downgrade() -> None:
    op.drop_index("ix_scoring_admin_audits_player_week", table_name="scoring_admin_audits")
    op.drop_index("ix_scoring_admin_audits_league_week", table_name="scoring_admin_audits")
    op.drop_index("ix_scoring_admin_audits_actor_user_id", table_name="scoring_admin_audits")
    op.drop_index("ix_scoring_admin_audits_action", table_name="scoring_admin_audits")
    op.drop_table("scoring_admin_audits")
