"""notification user id migration

Revision ID: 0012_notif_user_ids
Revises: 0011_roster_watchlists
Create Date: 2026-03-21 19:15:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0012_notif_user_ids"
down_revision = "0011_roster_watchlists"
branch_labels = None
depends_on = None


def _backfill_user_id(table_name: str) -> None:
    op.execute(
        sa.text(
            f"""
            UPDATE {table_name}
            SET user_id = (
                SELECT users.id
                FROM users
                WHERE CAST(users.id AS TEXT) = {table_name}.user_key
            )
            WHERE user_id IS NULL AND user_key IS NOT NULL
            """
        )
    )


def upgrade() -> None:
    with op.batch_alter_table("push_tokens") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_push_tokens_user_id_users",
            "users",
            ["user_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_push_tokens_user_id", ["user_id"], unique=False)
    _backfill_user_id("push_tokens")

    with op.batch_alter_table("notification_preferences") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_notification_preferences_user_id_users",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_index("ix_notification_preferences_user_id", ["user_id"], unique=False)
    _backfill_user_id("notification_preferences")

    with op.batch_alter_table("notification_logs") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_notification_logs_user_id_users",
            "users",
            ["user_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_notification_logs_user_id", ["user_id"], unique=False)
    _backfill_user_id("notification_logs")

    with op.batch_alter_table("notification_league_preferences") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_notification_league_preferences_user_id_users",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_index("ix_notification_league_preferences_user_id", ["user_id"], unique=False)
        batch_op.create_unique_constraint(
            "uq_notification_league_user_id",
            ["user_id", "league_id"],
        )
    _backfill_user_id("notification_league_preferences")


def downgrade() -> None:
    with op.batch_alter_table("notification_league_preferences") as batch_op:
        batch_op.drop_constraint("uq_notification_league_user_id", type_="unique")
        batch_op.drop_index("ix_notification_league_preferences_user_id")
        batch_op.drop_constraint("fk_notification_league_preferences_user_id_users", type_="foreignkey")
        batch_op.drop_column("user_id")

    with op.batch_alter_table("notification_logs") as batch_op:
        batch_op.drop_index("ix_notification_logs_user_id")
        batch_op.drop_constraint("fk_notification_logs_user_id_users", type_="foreignkey")
        batch_op.drop_column("user_id")

    with op.batch_alter_table("notification_preferences") as batch_op:
        batch_op.drop_index("ix_notification_preferences_user_id")
        batch_op.drop_constraint("fk_notification_preferences_user_id_users", type_="foreignkey")
        batch_op.drop_column("user_id")

    with op.batch_alter_table("push_tokens") as batch_op:
        batch_op.drop_index("ix_push_tokens_user_id")
        batch_op.drop_constraint("fk_push_tokens_user_id_users", type_="foreignkey")
        batch_op.drop_column("user_id")
