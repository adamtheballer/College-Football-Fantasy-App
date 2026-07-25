"""Repair databases stamped past the player biography migration without its columns.

Some legacy local databases recorded later Alembic revisions while the
``0045_player_sheet_bio_fields`` DDL was absent. This guarded reconciliation
keeps fresh databases unchanged and restores the current Player ORM contract
on affected environments.

Revision ID: 0061_reconcile_player_bio
Revises: 0060_projection_beta_hardening
"""

import sqlalchemy as sa
from alembic import op


revision = "0061_reconcile_player_bio"
down_revision = "0060_projection_beta_hardening"
branch_labels = None
depends_on = None


PLAYER_BIO_COLUMNS = (
    ("sheet_bio_height", sa.String(length=40)),
    ("sheet_bio_weight", sa.String(length=40)),
    ("sheet_bio_class", sa.String(length=30)),
    ("sheet_bio_birthplace", sa.String(length=300)),
    ("sheet_bio_source_sheet_id", sa.String(length=200)),
    ("sheet_bio_synced_at", sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("players")}
    for name, column_type in PLAYER_BIO_COLUMNS:
        if name not in existing:
            op.add_column("players", sa.Column(name, column_type, nullable=True))


def downgrade() -> None:
    # The migration cannot distinguish pre-existing columns from repaired
    # columns, so a downgrade intentionally preserves these nullable fields.
    pass
