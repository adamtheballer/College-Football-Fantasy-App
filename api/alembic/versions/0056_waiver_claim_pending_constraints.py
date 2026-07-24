"""Correct pending-claim uniqueness and reconcile legacy waiver indexes.

Revision ID: 0056_waiver_pending_claims
Revises: 0055_team_schedule_game_logs
"""

from alembic import op
import sqlalchemy as sa


revision = "0056_waiver_pending_claims"
down_revision = "0055_team_schedule_game_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 0052 made a terminal claim permanently reserve its old preference. Only
    # live pending claims must be unique so a cancelled or completed claim can
    # never block the manager's next claim in the same window.
    op.drop_constraint("uq_waiver_claims_team_window_preference", "waiver_claims", type_="unique")
    op.create_index(
        "uq_waiver_claims_pending_team_window_preference",
        "waiver_claims",
        ["team_id", "processing_window_id", "preference_order"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index(
        "uq_waiver_claims_pending_team_player_window",
        "waiver_claims",
        ["team_id", "add_player_id", "processing_window_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )
    # This legacy index is absent from ORM metadata and makes alembic check
    # report schema drift. It is superseded by ix_waiver_claims_window_status.
    op.execute("DROP INDEX IF EXISTS ix_waiver_claims_league_status_priority")


def downgrade() -> None:
    op.drop_index("uq_waiver_claims_pending_team_player_window", table_name="waiver_claims")
    op.drop_index("uq_waiver_claims_pending_team_window_preference", table_name="waiver_claims")
    op.create_unique_constraint(
        "uq_waiver_claims_team_window_preference",
        "waiver_claims",
        ["team_id", "processing_window_id", "preference_order"],
    )
