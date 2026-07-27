"""correct DeSean Bishop class

Revision ID: 0077_correct_desean_bishop_class
Revises: 0076_saturday_pick_6
"""

from alembic import op


revision = "0077_correct_desean_bishop_class"
down_revision = "0076_saturday_pick_6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The 2026 canonical-sheet row currently reports SR, but the verified roster
    # correction is Junior. Keep the raw sheet metadata untouched for auditability
    # while making the public player-card field authoritative.
    op.execute(
        """
        UPDATE players
        SET
            player_class = 'Junior',
            bio_source = 'manual_verified_override',
            bio_imported_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE
            external_id = 'cfb27:deseanbishop|tennessee|RB'
            AND name = 'DeSean Bishop'
            AND school = 'Tennessee'
            AND UPPER(position) = 'RB'
        """
    )


def downgrade() -> None:
    # Do not reintroduce the disputed source value during a rollback.
    pass
