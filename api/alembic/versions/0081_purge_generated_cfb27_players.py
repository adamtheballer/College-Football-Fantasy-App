"""remove generated CFB27-only players from the eligible player universe

Revision ID: 0081_purge_cfb27_rows
Revises: 0080_saturday_pick_live_scores
"""

from alembic import op
import sqlalchemy as sa


revision = "0081_purge_cfb27_rows"
down_revision = "0080_saturday_pick_live_scores"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The old CFB27 sync fabricated player records for every rating, including
    # non-Power 4 schools. Approved spreadsheet imports stamp this field, so a
    # null source identifies only the generated records and leaves real player
    # rows plus their history intact.
    op.execute(
        sa.text(
            """
            DELETE FROM players
            WHERE external_id LIKE 'cfb27:%'
              AND sheet_source_sheet_id IS NULL
            """
        )
    )


def downgrade() -> None:
    # Data purge is intentionally irreversible; deleted records were generated
    # from a rating file and were never approved player-sheet rows.
    pass
