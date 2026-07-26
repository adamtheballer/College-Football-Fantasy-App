"""Allow the rolling-priority option exposed by the league-creation UI.

The React league form has always submitted ``rolling`` for its "Rolling
Priority" choice.  The runtime schema and processing-run table accepted only
``faab`` and the legacy ``priority`` spelling, causing a database constraint
error after request validation.  Preserve the legacy spelling and explicitly
allow the UI contract on both tables.

Revision ID: 0074_rolling_waiver_priority
Revises: 0073_legacy_beta_schema
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0074_rolling_waiver_priority"
down_revision: str | Sequence[str] | None = "0073_legacy_beta_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _has_check_constraint(table_name: str, constraint_name: str) -> bool:
    return any(
        constraint["name"] == constraint_name
        for constraint in sa.inspect(op.get_bind()).get_check_constraints(table_name)
    )


def _replace_waiver_type_constraint(table_name: str, constraint_name: str) -> None:
    if not _has_table(table_name):
        return
    if _has_check_constraint(table_name, constraint_name):
        op.drop_constraint(constraint_name, table_name, type_="check")
    op.create_check_constraint(
        constraint_name,
        table_name,
        "waiver_type IN ('faab', 'priority', 'rolling')",
    )


def upgrade() -> None:
    _replace_waiver_type_constraint("league_settings", "ck_league_settings_waiver_type")
    _replace_waiver_type_constraint("waiver_processing_runs", "ck_waiver_processing_runs_waiver_type")


def downgrade() -> None:
    pass
