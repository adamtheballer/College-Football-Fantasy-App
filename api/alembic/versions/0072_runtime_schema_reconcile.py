"""Reconcile head-stamped beta runtime schema with active metadata.

Revision ID: 0072_runtime_schema_reconcile
Revises: 0071_waiver_settings_fix
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0072_runtime_schema_reconcile"
down_revision: str | Sequence[str] | None = "0071_waiver_settings_fix"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _has_column(table_name: str, column_name: str) -> bool:
    return any(
        column["name"] == column_name
        for column in sa.inspect(op.get_bind()).get_columns(table_name)
    )


def _create_application_instances_if_missing() -> None:
    if _has_table("application_instances"):
        return
    op.create_table(
        "application_instances",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("instance_uuid", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("environment", sa.String(length=32), nullable=False),
        sa.Column("schema_version", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("instance_uuid"),
    )


def _backfill_and_require_timestamp(table_name: str, column_name: str) -> None:
    if not _has_table(table_name) or not _has_column(table_name, column_name):
        return
    op.execute(sa.text(f"UPDATE {table_name} SET {column_name} = now() WHERE {column_name} IS NULL"))
    op.alter_column(
        table_name,
        column_name,
        existing_type=sa.DateTime(timezone=True),
        existing_server_default=sa.text("now()"),
        nullable=False,
    )


def upgrade() -> None:
    _create_application_instances_if_missing()

    for table_name in ("player_season_contexts", "team_season_ratings"):
        for column_name in ("created_at", "updated_at"):
            _backfill_and_require_timestamp(table_name, column_name)

    if _has_table("waiver_claims") and _has_column("waiver_claims", "waiver_period_id"):
        op.alter_column(
            "waiver_claims",
            "waiver_period_id",
            existing_type=sa.Integer(),
            nullable=True,
        )


def downgrade() -> None:
    pass
