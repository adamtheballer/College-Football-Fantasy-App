"""Persist deterministic postseason seeding evidence.

Revision ID: 0092_postseason_seeding_contract
Revises: 0091_durable_notification_outbox
"""

from alembic import op
import sqlalchemy as sa


revision = "0092_postseason_seeding_contract"
down_revision = "0091_durable_notification_outbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("teams", sa.Column("postseason_tiebreak_lot", sa.String(length=64), nullable=True))
    # Legacy teams receive an idempotent, persisted lot. New teams receive a
    # cryptographically generated lot in the league service before seeding.
    op.execute(
        "UPDATE teams SET postseason_tiebreak_lot = md5('legacy-postseason-lot:' || league_id || ':' || id) "
        "WHERE postseason_tiebreak_lot IS NULL"
    )
    op.create_index(
        "uq_teams_league_postseason_tiebreak_lot",
        "teams",
        ["league_id", "postseason_tiebreak_lot"],
        unique=True,
    )
    op.add_column("postseason_entries", sa.Column("seeding_trace_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("postseason_entries", "seeding_trace_json")
    op.drop_index("uq_teams_league_postseason_tiebreak_lot", table_name="teams")
    op.drop_column("teams", "postseason_tiebreak_lot")
