"""Reconcile head-stamped legacy league-settings waiver columns.

Revision ID: 0071_waiver_settings_fix
Revises: 0070_postseason_brackets
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0071_waiver_settings_fix"
down_revision: str | Sequence[str] | None = "0070_postseason_brackets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _columns() -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns("league_settings")}


def _add_required_column(name: str, column_type: sa.types.TypeEngine, default: str | sa.sql.ClauseElement) -> None:
    if name in _columns():
        return
    op.add_column(
        "league_settings",
        sa.Column(name, column_type, nullable=False, server_default=default),
    )
    op.alter_column("league_settings", name, existing_type=column_type, server_default=None)


def upgrade() -> None:
    _add_required_column("waiver_process_day", sa.Integer(), "2")
    _add_required_column("waiver_process_hour", sa.Integer(), "3")
    _add_required_column("faab_budget", sa.Integer(), "100")
    _add_required_column("allow_zero_dollar_bids", sa.Boolean(), sa.true())

    columns = _columns()
    legacy_to_canonical = (
        ("waiver_processing_weekday", "waiver_process_day"),
        ("waiver_processing_hour", "waiver_process_hour"),
        ("faab_starting_budget", "faab_budget"),
        ("allow_zero_faab_bids", "allow_zero_dollar_bids"),
    )
    for legacy_name, canonical_name in legacy_to_canonical:
        if legacy_name in columns:
            op.execute(
                sa.text(
                    f"UPDATE league_settings "
                    f"SET {canonical_name} = {legacy_name} "
                    f"WHERE {legacy_name} IS NOT NULL"
                )
            )


def downgrade() -> None:
    for name in (
        "allow_zero_dollar_bids",
        "faab_budget",
        "waiver_process_hour",
        "waiver_process_day",
    ):
        if name in _columns():
            op.drop_column("league_settings", name)
