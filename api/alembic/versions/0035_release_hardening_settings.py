"""add release-hardening league settings

Revision ID: 0035_release_hardening_settings
Revises: 0034_lineup_snapshot_kickoff_lock
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0035_release_settings"
down_revision: str | Sequence[str] | None = "0034_lineup_kickoff_lock"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("league_settings")}
    additions = [
        ("waiver_process_day", sa.Integer(), "2"),
        ("waiver_process_hour", sa.Integer(), "3"),
        ("faab_budget", sa.Integer(), "100"),
        ("allow_zero_dollar_bids", sa.Boolean(), sa.text("true")),
        ("waiver_tiebreaker", sa.String(length=50), "priority"),
        ("initial_waiver_priority_method", sa.String(length=50), "reverse_draft"),
        ("post_drop_waiver_hours", sa.Integer(), "24"),
    ]
    for name, column_type, default in additions:
        if name not in columns:
            op.add_column("league_settings", sa.Column(name, column_type, nullable=False, server_default=default))
            op.alter_column("league_settings", name, existing_type=column_type, server_default=None)
    if "next_waiver_run_at" not in columns:
        op.add_column("league_settings", sa.Column("next_waiver_run_at", sa.DateTime(timezone=True), nullable=True))
    if "trade_deadline_week" not in columns:
        op.add_column("league_settings", sa.Column("trade_deadline_week", sa.Integer(), nullable=True))
    if "trade_deadline_at" not in columns:
        op.add_column("league_settings", sa.Column("trade_deadline_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    for name in (
        "trade_deadline_at",
        "trade_deadline_week",
        "next_waiver_run_at",
        "post_drop_waiver_hours",
        "initial_waiver_priority_method",
        "waiver_tiebreaker",
        "allow_zero_dollar_bids",
        "faab_budget",
        "waiver_process_hour",
        "waiver_process_day",
    ):
        op.drop_column("league_settings", name)
