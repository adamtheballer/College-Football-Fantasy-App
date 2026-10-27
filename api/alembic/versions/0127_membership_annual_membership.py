"""annual_membership

Revision ID: 0127_membership
Revises: 0126_dynasty_2027
Create Date: 2026-10-27 14:39:45.906647
"""

from alembic import op
import sqlalchemy as sa

revision = "0127_membership"
down_revision = "0126_dynasty_2027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "membership_accounts",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("apple_account_token", sa.String(length=36), nullable=False),
        sa.Column("stripe_customer_id", sa.String(length=255), nullable=True),
        sa.Column("checkout_id", sa.String(length=255), nullable=True),
        sa.Column("checkout_url", sa.String(length=2000), nullable=True),
        sa.Column("checkout_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
        sa.UniqueConstraint("apple_account_token"),
        sa.UniqueConstraint("stripe_customer_id"),
    )
    op.create_table(
        "membership_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=10), nullable=False),
        sa.Column("event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("provider_subscription_id", sa.String(length=255), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider", "event_id", name="uq_membership_provider_event"
        ),
    )
    op.create_table(
        "membership_subscriptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("provider", sa.String(length=10), nullable=False),
        sa.Column("provider_subscription_id", sa.String(length=255), nullable=False),
        sa.Column("transaction_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False),
        sa.Column("provider_signed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "provider IN ('stripe','apple')", name="ck_membership_provider"
        ),
        sa.CheckConstraint(
            "status IN ('active','past_due','canceled','expired','refunded','incomplete')",
            name="ck_membership_status",
        ),
        sa.CheckConstraint("period_end >= period_start", name="ck_membership_period"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "provider_subscription_id",
            name="uq_membership_provider_subscription",
        ),
    )
    op.create_index(
        op.f("ix_membership_subscriptions_user_id"),
        "membership_subscriptions",
        ["user_id"],
        unique=False,
    )
    op.alter_column(
        "dynasty_franchises", "owner_user_id", existing_type=sa.INTEGER(), nullable=True
    )
    op.drop_constraint(
        op.f("dynasty_franchises_owner_user_id_fkey"),
        "dynasty_franchises",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "dynasty_franchises_owner_user_id_fkey",
        "dynasty_franchises",
        "users",
        ["owner_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.alter_column(
        "dynasty_leagues",
        "commissioner_user_id",
        existing_type=sa.INTEGER(),
        nullable=True,
    )
    op.drop_constraint(
        op.f("dynasty_leagues_commissioner_user_id_fkey"),
        "dynasty_leagues",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "dynasty_leagues_commissioner_user_id_fkey",
        "dynasty_leagues",
        "users",
        ["commissioner_user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Deleted managers cannot be recreated or silently reassigned.
    connection = op.get_bind()
    if connection.scalar(
        sa.text("SELECT count(*) FROM dynasty_franchises WHERE owner_user_id IS NULL")
    ) or connection.scalar(
        sa.text(
            "SELECT count(*) FROM dynasty_leagues WHERE commissioner_user_id IS NULL"
        )
    ):
        raise RuntimeError(
            "Cannot downgrade membership after dynasty manager deletion; preserve the nullable ownership records or restore a pre-deletion backup."
        )
    op.drop_constraint(
        "dynasty_leagues_commissioner_user_id_fkey",
        "dynasty_leagues",
        type_="foreignkey",
    )
    op.create_foreign_key(
        op.f("dynasty_leagues_commissioner_user_id_fkey"),
        "dynasty_leagues",
        "users",
        ["commissioner_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.alter_column(
        "dynasty_leagues",
        "commissioner_user_id",
        existing_type=sa.INTEGER(),
        nullable=False,
    )
    op.drop_constraint(
        "dynasty_franchises_owner_user_id_fkey",
        "dynasty_franchises",
        type_="foreignkey",
    )
    op.create_foreign_key(
        op.f("dynasty_franchises_owner_user_id_fkey"),
        "dynasty_franchises",
        "users",
        ["owner_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.alter_column(
        "dynasty_franchises",
        "owner_user_id",
        existing_type=sa.INTEGER(),
        nullable=False,
    )
    op.drop_index(
        op.f("ix_membership_subscriptions_user_id"),
        table_name="membership_subscriptions",
    )
    op.drop_table("membership_subscriptions")
    op.drop_table("membership_events")
    op.drop_table("membership_accounts")
