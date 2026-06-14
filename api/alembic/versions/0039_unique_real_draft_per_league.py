"""unique real draft per league

Revision ID: 0039_unique_real_draft_per_league
Revises: 0038_nullable_mock_pick_seat
Create Date: 2026-06-12 00:00:00.000000
"""

from alembic import op


revision = "0039_unique_real_draft_per_league"
down_revision = "0038_nullable_mock_pick_seat"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint("uq_drafts_league_id", "drafts", ["league_id"])


def downgrade() -> None:
    op.drop_constraint("uq_drafts_league_id", "drafts", type_="unique")
