"""reconcile release audit timestamp nullability

Revision ID: 0082_release_audit_timestamps
Revises: 0081_purge_cfb27_rows
"""

from alembic import op
import sqlalchemy as sa


revision = "0082_release_audit_timestamps"
down_revision = "0081_purge_cfb27_rows"
branch_labels = None
depends_on = None


_TABLES = ("league_player_events", "player_trade_values")
_COLUMNS = ("created_at", "updated_at")


def upgrade() -> None:
    # 0078/0079 created these audit fields with server defaults but omitted
    # nullable=False. Backfill defensively before tightening the constraint so
    # an existing beta database can upgrade without data loss.
    for table_name in _TABLES:
        for column_name in _COLUMNS:
            op.execute(
                sa.text(
                    f"UPDATE {table_name} SET {column_name} = CURRENT_TIMESTAMP "
                    f"WHERE {column_name} IS NULL"
                )
            )
            op.alter_column(table_name, column_name, existing_type=sa.DateTime(timezone=True), nullable=False)


def downgrade() -> None:
    for table_name in _TABLES:
        for column_name in _COLUMNS:
            op.alter_column(table_name, column_name, existing_type=sa.DateTime(timezone=True), nullable=True)
