"""league creation flow tables

Revision ID: 0006_league_flow
Revises: 0005_feature_support
Create Date: 2026-03-08 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "0006_league_flow"
down_revision = "0005_feature_support"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=200), nullable=False, unique=True),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.String(length=200), nullable=False),
        sa.Column("api_token", sa.String(length=100), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_token", "users", ["api_token"])

    op.add_column("leagues", sa.Column("commissioner_user_id", sa.Integer(), nullable=True))
    op.add_column("leagues", sa.Column("season_year", sa.Integer(), nullable=False, server_default="2026"))
    op.add_column("leagues", sa.Column("max_teams", sa.Integer(), nullable=False, server_default="12"))
    op.add_column("leagues", sa.Column("is_private", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("leagues", sa.Column("invite_code", sa.String(length=30), nullable=True))
    op.add_column("leagues", sa.Column("description", sa.String(length=500), nullable=True))
    op.add_column("leagues", sa.Column("icon_url", sa.String(length=500), nullable=True))
    op.add_column("leagues", sa.Column("status", sa.String(length=30), nullable=False, server_default="pre_draft"))
    op.create_foreign_key(
        "fk_leagues_commissioner_user_id",
        "leagues",
        "users",
        ["commissioner_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("teams", sa.Column("owner_user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_teams_owner_user_id",
        "teams",
        "users",
        ["owner_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "league_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("league_id", sa.Integer(), sa.ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(length=30), nullable=False, server_default="member"),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("league_id", "user_id", name="uq_league_members_league_user"),
    )
    op.create_index("ix_league_members_league_id", "league_members", ["league_id"])
    op.create_index("ix_league_members_user_id", "league_members", ["user_id"])

    op.create_table(
        "league_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("league_id", sa.Integer(), sa.ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scoring_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("roster_slots_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("playoff_teams", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("waiver_type", sa.String(length=50), nullable=False, server_default="FAAB"),
        sa.Column("trade_review_type", sa.String(length=50), nullable=False, server_default="commissioner"),
        sa.Column("superflex_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("kicker_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("defense_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_league_settings_league_id", "league_settings", ["league_id"])

    op.create_table(
        "league_invites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("league_id", sa.Integer(), sa.ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False, unique=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_league_invites_code", "league_invites", ["code"])
    op.create_index("ix_league_invites_league_id", "league_invites", ["league_id"])

    op.create_table(
        "drafts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("league_id", sa.Integer(), sa.ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("draft_datetime_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone", sa.String(length=50), nullable=False, server_default="UTC"),
        sa.Column("draft_type", sa.String(length=30), nullable=False, server_default="snake"),
        sa.Column("pick_timer_seconds", sa.Integer(), nullable=False, server_default="90"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="scheduled"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_drafts_league_id", "drafts", ["league_id"])
    op.create_index("ix_drafts_datetime", "drafts", ["draft_datetime_utc"])

    op.create_table(
        "scheduled_notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("league_id", sa.Integer(), sa.ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("notification_type", sa.String(length=50), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_scheduled_notifications_league_id", "scheduled_notifications", ["league_id"])
    op.create_index("ix_scheduled_notifications_user_id", "scheduled_notifications", ["user_id"])
    op.create_index("ix_scheduled_notifications_type", "scheduled_notifications", ["notification_type"])

    op.add_column("notification_preferences", sa.Column("push_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("notification_preferences", sa.Column("email_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("notification_preferences", sa.Column("draft_alerts", sa.Boolean(), nullable=False, server_default=sa.text("true")))


def downgrade() -> None:
    op.drop_column("notification_preferences", "draft_alerts")
    op.drop_column("notification_preferences", "email_enabled")
    op.drop_column("notification_preferences", "push_enabled")

    op.drop_index("ix_scheduled_notifications_type", table_name="scheduled_notifications")
    op.drop_index("ix_scheduled_notifications_user_id", table_name="scheduled_notifications")
    op.drop_index("ix_scheduled_notifications_league_id", table_name="scheduled_notifications")
    op.drop_table("scheduled_notifications")

    op.drop_index("ix_drafts_datetime", table_name="drafts")
    op.drop_index("ix_drafts_league_id", table_name="drafts")
    op.drop_table("drafts")

    op.drop_index("ix_league_invites_league_id", table_name="league_invites")
    op.drop_index("ix_league_invites_code", table_name="league_invites")
    op.drop_table("league_invites")

    op.drop_index("ix_league_settings_league_id", table_name="league_settings")
    op.drop_table("league_settings")

    op.drop_index("ix_league_members_user_id", table_name="league_members")
    op.drop_index("ix_league_members_league_id", table_name="league_members")
    op.drop_table("league_members")

    op.drop_constraint("fk_teams_owner_user_id", "teams", type_="foreignkey")
    op.drop_column("teams", "owner_user_id")

    op.drop_constraint("fk_leagues_commissioner_user_id", "leagues", type_="foreignkey")
    op.drop_column("leagues", "status")
    op.drop_column("leagues", "invite_code")
    op.drop_column("leagues", "icon_url")
    op.drop_column("leagues", "description")
    op.drop_column("leagues", "is_private")
    op.drop_column("leagues", "max_teams")
    op.drop_column("leagues", "season_year")
    op.drop_column("leagues", "commissioner_user_id")

    op.drop_index("ix_users_token", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
