"""draft picks

Revision ID: 0010_draft_picks
Revises: 0009_player_image_urls
Create Date: 2026-03-21 02:15:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0010_draft_picks"
down_revision = "0009_player_image_urls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "draft_picks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("draft_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("made_by_user_id", sa.Integer(), nullable=True),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("round_pick", sa.Integer(), nullable=False),
        sa.Column("overall_pick", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["draft_id"], ["drafts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["made_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("draft_id", "overall_pick", name="uq_draft_picks_draft_overall_pick"),
        sa.UniqueConstraint("draft_id", "player_id", name="uq_draft_picks_draft_player"),
    )
    op.create_index("ix_draft_picks_draft_id", "draft_picks", ["draft_id"], unique=False)
    op.create_index("ix_draft_picks_team_id", "draft_picks", ["team_id"], unique=False)
    op.create_index("ix_draft_picks_player_id", "draft_picks", ["player_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_draft_picks_player_id", table_name="draft_picks")
    op.drop_index("ix_draft_picks_team_id", table_name="draft_picks")
    op.drop_index("ix_draft_picks_draft_id", table_name="draft_picks")
    op.drop_table("draft_picks")
