"""Move canonical waiver processing to Sunday.

Revision ID: 0103_sunday_waivers
Revises: 0102_postseason_playoffs
"""

from alembic import op
import sqlalchemy as sa


revision = "0103_sunday_waivers"
down_revision = "0102_postseason_playoffs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The beta schedule is global: weekly bids clear Sunday before the next
    # Tuesday--Saturday game window. Clear cached run times so the worker
    # recalculates each league's Sunday timestamp in its own timezone.
    op.execute("UPDATE league_settings SET waiver_processing_weekday = 6, next_waiver_run_at = NULL")
    op.alter_column(
        "league_settings",
        "waiver_processing_weekday",
        existing_type=sa.Integer(),
        server_default="6",
    )


def downgrade() -> None:
    # Do not rewrite managers' migrated schedules on rollback; only restore
    # the historical schema default for newly inserted legacy rows.
    op.alter_column(
        "league_settings",
        "waiver_processing_weekday",
        existing_type=sa.Integer(),
        server_default="1",
    )
