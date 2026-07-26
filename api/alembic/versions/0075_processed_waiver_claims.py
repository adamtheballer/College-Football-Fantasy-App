"""Allow the successful waiver-claim status written by the processor.

The processor marks a completed claim ``processed``. The preserved beta schema
only allowed historical terminal values such as ``won`` and ``lost``, so a
successful transaction was rolled back by the database check constraint and
reported as a generic failure. This forward migration aligns persisted state
with the active processor without altering historical claim rows.

Revision ID: 0075_processed_waiver_claims
Revises: 0074_rolling_waiver_priority
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0075_processed_waiver_claims"
down_revision: str | Sequence[str] | None = "0074_rolling_waiver_priority"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_check_constraint(table_name: str, constraint_name: str) -> bool:
    return any(
        constraint["name"] == constraint_name
        for constraint in sa.inspect(op.get_bind()).get_check_constraints(table_name)
    )


def upgrade() -> None:
    if _has_check_constraint("waiver_claims", "ck_waiver_claims_status"):
        op.drop_constraint("ck_waiver_claims_status", "waiver_claims", type_="check")
    op.create_check_constraint(
        "ck_waiver_claims_status",
        "waiver_claims",
        "status IN ('pending', 'won', 'lost', 'cancelled', 'invalid', "
        "'insufficient_budget', 'roster_full', 'player_unavailable', 'skipped', 'processed', 'failed')",
    )


def downgrade() -> None:
    pass
