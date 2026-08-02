"""reconcile beta access table with ORM metadata

Revision ID: 0084_beta_access_schema
Revises: 0083_beta_access

``0083_beta_access`` was released with nullable timestamp columns, plus a
unique constraint and a separate non-unique index for each identity field.
The ORM intentionally models each identity field as a named unique index.
This forward-only migration aligns the live schema without rewriting the
released migration or changing any beta-access records.
"""

from alembic import op
import sqlalchemy as sa


revision = "0084_beta_access_schema"
down_revision = "0083_beta_access"
branch_labels = None
depends_on = None


_UNIQUE_COLUMNS = (
    ("source_waitlist_id", "beta_access_codes_source_waitlist_id_key"),
    ("email", "beta_access_codes_email_key"),
    ("code_hmac", "beta_access_codes_code_hmac_key"),
    ("redeemed_user_id", "beta_access_codes_redeemed_user_id_key"),
)


def _model_index_name(column_name: str) -> str:
    return f"ix_beta_access_codes_{column_name}"


def _temporary_index_name(column_name: str) -> str:
    return f"uq_beta_access_codes_{column_name}_reconcile"


def upgrade() -> None:
    # Existing 0083 rows may predate the model's non-null timestamp contract.
    # Backfill first so a live beta database upgrades without losing records.
    op.execute(
        sa.text(
            "UPDATE beta_access_codes "
            "SET created_at = CURRENT_TIMESTAMP "
            "WHERE created_at IS NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE beta_access_codes "
            "SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP) "
            "WHERE updated_at IS NULL"
        )
    )
    for column_name in ("created_at", "updated_at"):
        op.alter_column(
            "beta_access_codes",
            column_name,
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
        )

    # Keep a unique structure in place throughout each reconciliation.  The
    # temporary index is renamed only after the released constraint and stale
    # non-unique index have been removed.
    for column_name, constraint_name in _UNIQUE_COLUMNS:
        model_index_name = _model_index_name(column_name)
        temporary_index_name = _temporary_index_name(column_name)
        op.create_index(temporary_index_name, "beta_access_codes", [column_name], unique=True)
        op.drop_constraint(constraint_name, "beta_access_codes", type_="unique")
        op.drop_index(model_index_name, table_name="beta_access_codes")
        op.execute(sa.text(f"ALTER INDEX {temporary_index_name} RENAME TO {model_index_name}"))


def downgrade() -> None:
    # Restore the exact 0083 layout for a deliberate rollback.  Downgrades run
    # under Alembic's transactional DDL, so each field remains unique while
    # the representation changes back to a constraint plus a normal index.
    for column_name, constraint_name in _UNIQUE_COLUMNS:
        model_index_name = _model_index_name(column_name)
        op.drop_index(model_index_name, table_name="beta_access_codes")
        op.create_unique_constraint(constraint_name, "beta_access_codes", [column_name])
        op.create_index(model_index_name, "beta_access_codes", [column_name])

    for column_name in ("created_at", "updated_at"):
        op.alter_column(
            "beta_access_codes",
            column_name,
            existing_type=sa.DateTime(timezone=True),
            nullable=True,
        )
