"""challenge experiences

Revision ID: 0125_challenge_experiences
Revises: 0124_release_notice
Create Date: 2026-10-17 17:59:10.555833
"""

from alembic import op
import sqlalchemy as sa


revision = "0125_challenge_experiences"
down_revision = "0124_release_notice"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "challenge_analytics_preferences",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
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
    )
    # Additive mode facts; existing competition and entry IDs are preserved.
    op.create_table(
        "challenge_survivor_series",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("start_week", sa.Integer(), nullable=False),
        sa.Column("end_week", sa.Integer(), nullable=False),
        sa.Column("entry_open_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_lock_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
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
            "start_week >= 1 AND end_week >= start_week AND end_week <= 15",
            name="ck_survivor_series_weeks",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_challenge_survivor_series_season"),
        "challenge_survivor_series",
        ["season"],
        unique=False,
    )
    op.create_table(
        "challenge_creators",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("links", sa.JSON(), nullable=False),
        sa.Column("authorized", sa.Boolean(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
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
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "challenge_fan_memberships",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("school_name", sa.String(length=200), nullable=False),
        sa.Column("conference", sa.String(length=50), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["school_id"], ["college_teams.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "season", "week", name="uq_challenge_fan_week"),
    )
    op.create_index(
        "ix_challenge_fan_school_week",
        "challenge_fan_memberships",
        ["season", "week", "school_id"],
        unique=False,
    )
    op.create_table(
        "challenge_management_audits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("resource", sa.String(length=40), nullable=False),
        sa.Column("resource_id", sa.Integer(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "challenge_survivor_enrollments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("series_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["series_id"], ["challenge_survivor_series.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("series_id", "user_id", name="uq_survivor_series_user"),
    )
    op.create_index(
        op.f("ix_challenge_survivor_enrollments_series_id"),
        "challenge_survivor_enrollments",
        ["series_id"],
        unique=False,
    )
    op.create_table(
        "challenge_creator_picks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("challenge_id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("team", sa.String(length=200), nullable=False),
        sa.ForeignKeyConstraint(
            ["challenge_id"], ["weekly_challenges.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "challenge_id", "game_id", name="uq_challenge_creator_pick"
        ),
    )
    op.create_index(
        op.f("ix_challenge_creator_picks_challenge_id"),
        "challenge_creator_picks",
        ["challenge_id"],
        unique=False,
    )
    op.create_table(
        "challenge_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dedupe_key", sa.String(length=180), nullable=False),
        sa.Column("challenge_id", sa.Integer(), nullable=True),
        sa.Column("creator_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["challenge_id"], ["weekly_challenges.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"], ["challenge_creators.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key"),
    )
    op.create_index(
        "ix_challenge_events_analytics",
        "challenge_events",
        ["challenge_id", "event_type", "at"],
        unique=False,
    )
    op.create_table(
        "challenge_experiences",
        sa.Column("challenge_id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=True),
        sa.Column("series_id", sa.Integer(), nullable=True),
        sa.Column("entry_open_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["challenge_id"], ["weekly_challenges.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"], ["challenge_creators.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["series_id"], ["challenge_survivor_series.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("challenge_id"),
    )
    op.create_index(
        op.f("ix_challenge_experiences_creator_id"),
        "challenge_experiences",
        ["creator_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_challenge_experiences_series_id"),
        "challenge_experiences",
        ["series_id"],
        unique=False,
    )
    op.create_table(
        "challenge_game_decisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("challenge_id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column(
            "active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
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
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["challenge_id"], ["weekly_challenges.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "challenge_id", "game_id", name="uq_challenge_game_decision"
        ),
    )
    op.create_index(
        op.f("ix_challenge_game_decisions_challenge_id"),
        "challenge_game_decisions",
        ["challenge_id"],
        unique=False,
    )
    op.create_table(
        "challenge_salaries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("challenge_id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("salary", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.CheckConstraint(
            "salary > 0 AND salary <= 100", name="ck_challenge_salary_budget"
        ),
        sa.ForeignKeyConstraint(
            ["challenge_id"], ["weekly_challenges.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "challenge_id", "player_id", name="uq_challenge_salary_player"
        ),
    )
    op.create_index(
        op.f("ix_challenge_salaries_challenge_id"),
        "challenge_salaries",
        ["challenge_id"],
        unique=False,
    )
    op.create_table(
        "challenge_entry_schools",
        sa.Column("entry_id", sa.Integer(), nullable=False),
        sa.Column("membership_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["entry_id"], ["challenge_entries.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["membership_id"], ["challenge_fan_memberships.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("entry_id"),
    )
    op.create_index(
        op.f("ix_challenge_entry_schools_membership_id"),
        "challenge_entry_schools",
        ["membership_id"],
        unique=False,
    )
    op.create_table(
        "challenge_survivor_picks",
        sa.Column("entry_id", sa.Integer(), nullable=False),
        sa.Column("enrollment_id", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("school_key", sa.String(length=200), nullable=False),
        sa.Column("outcome", sa.String(length=24), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["enrollment_id"], ["challenge_survivor_enrollments.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["entry_id"], ["challenge_entries.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("entry_id"),
        sa.UniqueConstraint(
            "enrollment_id", "school_key", name="uq_survivor_pick_school"
        ),
        sa.UniqueConstraint("enrollment_id", "week", name="uq_survivor_pick_week"),
    )
    op.create_index(
        op.f("ix_challenge_survivor_picks_enrollment_id"),
        "challenge_survivor_picks",
        ["enrollment_id"],
        unique=False,
    )
    op.add_column(
        "challenge_slate_games",
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "weekly_challenges",
        sa.Column(
            "variant", sa.String(length=80), server_default="primary", nullable=False
        ),
    )
    op.drop_constraint(
        op.f("uq_weekly_challenge_kind"), "weekly_challenges", type_="unique"
    )
    op.create_unique_constraint(
        "uq_weekly_challenge_variant",
        "weekly_challenges",
        ["round_id", "kind", "variant"],
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # A rollback cannot discard competition history, salaries, allegiance or audits.
    bind = op.get_bind()
    for table in (
        "challenge_experiences",
        "challenge_creators",
        "challenge_survivor_series",
        "challenge_fan_memberships",
        "challenge_management_audits",
        "challenge_events",
        "challenge_analytics_preferences",
    ):
        if bind.execute(sa.text(f"SELECT EXISTS (SELECT 1 FROM {table})")).scalar():
            raise RuntimeError(
                "Challenge experience history exists; preserve the schema or export/migrate it explicitly."
            )
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(
        "uq_weekly_challenge_variant", "weekly_challenges", type_="unique"
    )
    op.create_unique_constraint(
        op.f("uq_weekly_challenge_kind"),
        "weekly_challenges",
        ["round_id", "kind"],
        postgresql_nulls_not_distinct=False,
    )
    op.drop_column("weekly_challenges", "variant")
    op.drop_column("challenge_slate_games", "locked_at")
    op.drop_index(
        op.f("ix_challenge_survivor_picks_enrollment_id"),
        table_name="challenge_survivor_picks",
    )
    op.drop_table("challenge_survivor_picks")
    op.drop_index(
        op.f("ix_challenge_entry_schools_membership_id"),
        table_name="challenge_entry_schools",
    )
    op.drop_table("challenge_entry_schools")
    op.drop_index(
        op.f("ix_challenge_salaries_challenge_id"), table_name="challenge_salaries"
    )
    op.drop_table("challenge_salaries")
    op.drop_index(
        op.f("ix_challenge_game_decisions_challenge_id"),
        table_name="challenge_game_decisions",
    )
    op.drop_table("challenge_game_decisions")
    op.drop_index(
        op.f("ix_challenge_experiences_series_id"), table_name="challenge_experiences"
    )
    op.drop_index(
        op.f("ix_challenge_experiences_creator_id"), table_name="challenge_experiences"
    )
    op.drop_table("challenge_experiences")
    op.drop_index("ix_challenge_events_analytics", table_name="challenge_events")
    op.drop_table("challenge_events")
    op.drop_index(
        op.f("ix_challenge_creator_picks_challenge_id"),
        table_name="challenge_creator_picks",
    )
    op.drop_table("challenge_creator_picks")
    op.drop_index(
        op.f("ix_challenge_survivor_enrollments_series_id"),
        table_name="challenge_survivor_enrollments",
    )
    op.drop_table("challenge_survivor_enrollments")
    op.drop_table("challenge_management_audits")
    op.drop_index(
        "ix_challenge_fan_school_week", table_name="challenge_fan_memberships"
    )
    op.drop_table("challenge_fan_memberships")
    op.drop_table("challenge_creators")
    op.drop_index(
        op.f("ix_challenge_survivor_series_season"),
        table_name="challenge_survivor_series",
    )
    op.drop_table("challenge_survivor_series")
    op.drop_table("challenge_analytics_preferences")
    # ### end Alembic commands ###
