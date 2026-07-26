"""Create preserved beta schema on clean migration paths.

The historical beta database contains schedule, player-role, player-data, and
waiver-lifecycle structures from release branches whose original migrations
were intentionally retired.  Migration 0072 reconciles those structures when
they already exist.  This follow-up makes a clean database converge to the
same schema without deleting or rewriting the existing beta data.

Revision ID: 0073_legacy_beta_schema
Revises: 0072_runtime_schema_reconcile
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0073_legacy_beta_schema"
down_revision: str | Sequence[str] | None = "0072_runtime_schema_reconcile"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _has_table(name: str) -> bool:
    return _inspector().has_table(name)


def _has_column(table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in _inspector().get_columns(table_name))


def _has_index(table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in _inspector().get_indexes(table_name))


def _has_unique_constraint(table_name: str, constraint_name: str) -> bool:
    return any(
        constraint["name"] == constraint_name
        for constraint in _inspector().get_unique_constraints(table_name)
    )


def _has_foreign_key(table_name: str, constraint_name: str) -> bool:
    return any(
        foreign_key["name"] == constraint_name
        for foreign_key in _inspector().get_foreign_keys(table_name)
    )


def _has_check_constraint(table_name: str, constraint_name: str) -> bool:
    return any(
        constraint["name"] == constraint_name
        for constraint in _inspector().get_check_constraints(table_name)
    )


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if not _has_column(table_name, column.name):
        op.add_column(table_name, column)


def _create_index_if_missing(name: str, table_name: str, columns: list[str], **kwargs: object) -> None:
    if not _has_index(table_name, name):
        op.create_index(name, table_name, columns, **kwargs)


def _create_check_if_missing(table_name: str, name: str, condition: str) -> None:
    if not _has_check_constraint(table_name, name):
        op.create_check_constraint(name, table_name, condition)


def _create_database_metadata_if_missing() -> None:
    if _has_table("database_metadata"):
        return
    op.create_table(
        "database_metadata",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("instance_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("instance_id"),
    )


def _create_player_role_snapshots_if_missing() -> None:
    if _has_table("player_role_snapshots"):
        return
    op.create_table(
        "player_role_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="manual"),
        sa.Column("school", sa.String(length=200), nullable=False),
        sa.Column("position", sa.String(length=10), nullable=False),
        sa.Column("depth_order", sa.Integer(), nullable=True),
        sa.Column("role_status", sa.String(length=30), nullable=False, server_default="unknown"),
        sa.Column("snap_share", sa.Float(), nullable=True),
        sa.Column("route_participation", sa.Float(), nullable=True),
        sa.Column("target_share", sa.Float(), nullable=True),
        sa.Column("carry_share", sa.Float(), nullable=True),
        sa.Column("red_zone_share", sa.Float(), nullable=True),
        sa.Column("goal_line_share", sa.Float(), nullable=True),
        sa.Column("recent_usage_trend", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("player_id", "season", "week", name="uq_player_role_snapshot_week"),
    )
    op.create_index("ix_player_role_snapshot_player_id", "player_role_snapshots", ["player_id"])
    op.create_index("ix_player_role_snapshot_season_week", "player_role_snapshots", ["season", "week"])
    op.create_index("ix_player_role_snapshot_school_position", "player_role_snapshots", ["school", "position"])


def _create_waiver_periods_if_missing() -> None:
    if _has_table("waiver_periods"):
        return
    op.create_table(
        "waiver_periods",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("window_key", sa.String(length=120), nullable=False),
        sa.Column("opens_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closes_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processes_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="scheduled"),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "status IN ('scheduled', 'open', 'locked', 'processing', 'completed', 'failed')",
            name="ck_waiver_periods_status",
        ),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("league_id", "season", "week", "window_key", name="uq_waiver_periods_league_window"),
    )
    op.create_index("ix_waiver_periods_due", "waiver_periods", ["processes_at", "status"])
    op.create_index("ix_waiver_periods_league_status", "waiver_periods", ["league_id", "status"])


def _create_waiver_processing_runs_if_missing() -> None:
    if _has_table("waiver_processing_runs"):
        return
    op.create_table(
        "waiver_processing_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("window_key", sa.String(length=120), nullable=False),
        sa.Column("waiver_type", sa.String(length=20), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("claims_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("claims_won", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("waiver_period_id", sa.Integer(), nullable=False),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("waiver_type IN ('faab', 'priority')", name="ck_waiver_processing_runs_waiver_type"),
        sa.CheckConstraint("status IN ('pending', 'running', 'completed', 'failed')", name="ck_waiver_processing_runs_status"),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["waiver_period_id"],
            ["waiver_periods.id"],
            name="fk_waiver_processing_runs_period",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_waiver_processing_runs_idempotency_key"),
        sa.UniqueConstraint("waiver_period_id", name="uq_waiver_processing_runs_period"),
        sa.UniqueConstraint("league_id", "season", "week", "window_key", name="uq_waiver_processing_runs_window"),
    )
    op.create_index("ix_waiver_processing_runs_due", "waiver_processing_runs", ["scheduled_for", "status"])


def _create_player_waiver_availability_if_missing() -> None:
    if _has_table("player_waiver_availability"):
        return
    op.create_table(
        "player_waiver_availability",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False, server_default="waivers"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_transaction_id", sa.Integer(), nullable=True),
        sa.Column("dropped_by_team_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("waiver_period_id", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "state IN ('waivers', 'free_agent', 'waiver_locked', 'claim_pending', 'rostered', 'game_locked')",
            name="ck_player_waiver_availability_state",
        ),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_transaction_id"], ["transactions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["dropped_by_team_id"], ["teams.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["waiver_period_id"],
            ["waiver_periods.id"],
            name="fk_player_waiver_availability_period",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("league_id", "player_id", name="uq_player_waiver_availability_league_player"),
    )
    op.create_index(
        "ix_player_waiver_availability_due",
        "player_waiver_availability",
        ["league_id", "state", "available_at"],
    )


def _reconcile_existing_columns() -> None:
    _add_column_if_missing(
        "defense_ratings",
        sa.Column("pass_pressure_multiplier", sa.Float(), nullable=False, server_default="1"),
    )

    for column in (
        sa.Column("waiver_processing_weekday", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("waiver_processing_hour", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("waiver_timezone", sa.String(length=64), nullable=False, server_default="America/New_York"),
        sa.Column("faab_starting_budget", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("allow_zero_faab_bids", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("waiver_initialized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("waivers_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("free_agent_mode", sa.String(length=40), nullable=False, server_default="after_waivers_clear"),
    ):
        _add_column_if_missing("league_settings", column)

    for column in (
        sa.Column("espn_height_inches", sa.Integer(), nullable=True),
        sa.Column("espn_birthplace_city", sa.String(length=120), nullable=True),
        sa.Column("espn_birthplace_state", sa.String(length=120), nullable=True),
        sa.Column("espn_birthplace_country", sa.String(length=120), nullable=True),
        sa.Column("espn_hometown", sa.String(length=300), nullable=True),
        sa.Column("espn_date_of_birth", sa.Date(), nullable=True),
        sa.Column("espn_source_url", sa.String(length=500), nullable=True),
        sa.Column("depth_chart_position", sa.String(length=20), nullable=True),
        sa.Column("depth_order", sa.Integer(), nullable=True),
        sa.Column("bio_source", sa.String(length=80), nullable=True),
        sa.Column("bio_source_sheet_id", sa.String(length=80), nullable=True),
        sa.Column("bio_source_row", sa.Integer(), nullable=True),
        sa.Column("bio_imported_at", sa.DateTime(timezone=True), nullable=True),
    ):
        _add_column_if_missing("players", column)

    _add_column_if_missing("projection_explanations", sa.Column("components", sa.JSON(), nullable=True))
    _add_column_if_missing(
        "users",
        sa.Column("auth_version", sa.Integer(), nullable=False, server_default="1"),
    )

    for column in (
        sa.Column("season", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processing_week", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processing_window_id", sa.String(length=120), nullable=False, server_default="legacy"),
        sa.Column("processing_run_id", sa.Integer(), nullable=True),
        sa.Column("preference_order", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("winning_bid", sa.Integer(), nullable=True),
        sa.Column("prior_priority", sa.Integer(), nullable=True),
        sa.Column("resulting_priority", sa.Integer(), nullable=True),
        sa.Column("failure_code", sa.String(length=80), nullable=True),
        sa.Column("waiver_period_id", sa.Integer(), nullable=True),
    ):
        _add_column_if_missing("waiver_claims", column)

    _create_index_if_missing("ix_waiver_claims_period_status", "waiver_claims", ["waiver_period_id", "status"])
    _create_index_if_missing(
        "ix_waiver_claims_window_status",
        "waiver_claims",
        ["league_id", "processing_window_id", "status"],
    )
    _create_index_if_missing(
        "uq_waiver_claims_pending_team_period_player",
        "waiver_claims",
        ["team_id", "waiver_period_id", "add_player_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )
    _create_index_if_missing(
        "uq_waiver_claims_pending_team_period_preference",
        "waiver_claims",
        ["team_id", "waiver_period_id", "preference_order"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )
    _create_index_if_missing(
        "uq_waiver_claims_player_period_winner",
        "waiver_claims",
        ["league_id", "add_player_id", "waiver_period_id"],
        unique=True,
        postgresql_where=sa.text("status = 'won'"),
    )

    if not _has_foreign_key("waiver_claims", "fk_waiver_claims_processing_run"):
        op.create_foreign_key(
            "fk_waiver_claims_processing_run",
            "waiver_claims",
            "waiver_processing_runs",
            ["processing_run_id"],
            ["id"],
            ondelete="SET NULL",
        )
    if not _has_foreign_key("waiver_claims", "fk_waiver_claims_period"):
        op.create_foreign_key(
            "fk_waiver_claims_period",
            "waiver_claims",
            "waiver_periods",
            ["waiver_period_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    if not _has_unique_constraint("waiver_priorities", "uq_waiver_priorities_league_priority"):
        op.create_unique_constraint(
            "uq_waiver_priorities_league_priority",
            "waiver_priorities",
            ["league_id", "priority"],
        )

    _create_check_if_missing("waiver_claims", "ck_waiver_claims_faab_bid_nonnegative", "faab_bid >= 0")
    _create_check_if_missing("waiver_claims", "ck_waiver_claims_preference_order_positive", "preference_order > 0")
    _create_check_if_missing(
        "waiver_claims",
        "ck_waiver_claims_status",
        "status IN ('pending', 'won', 'lost', 'cancelled', 'invalid', 'insufficient_budget', "
        "'roster_full', 'player_unavailable', 'skipped', 'failed')",
    )
    _create_check_if_missing("waiver_priorities", "ck_waiver_priorities_priority_positive", "priority > 0")
    _create_check_if_missing("waiver_priorities", "ck_waiver_priorities_faab_budget_nonnegative", "faab_budget >= 0")
    _create_check_if_missing("waiver_priorities", "ck_waiver_priorities_faab_spent_nonnegative", "faab_spent >= 0")
    _create_check_if_missing("waiver_priorities", "ck_waiver_priorities_faab_remaining_nonnegative", "faab_spent <= faab_budget")
    _create_check_if_missing("league_settings", "ck_league_settings_waiver_type", "waiver_type IN ('faab', 'priority')")
    _create_check_if_missing("league_settings", "ck_league_settings_faab_starting_budget", "faab_starting_budget >= 0")
    _create_check_if_missing("league_settings", "ck_league_settings_waiver_processing_weekday", "waiver_processing_weekday BETWEEN 0 AND 6")
    _create_check_if_missing("league_settings", "ck_league_settings_waiver_processing_hour", "waiver_processing_hour BETWEEN 0 AND 23")
    _create_check_if_missing("league_settings", "ck_league_settings_post_drop_waiver_hours", "post_drop_waiver_hours >= 0")
    _create_check_if_missing("league_settings", "ck_league_settings_free_agent_mode", "free_agent_mode = 'after_waivers_clear'")


def upgrade() -> None:
    _create_database_metadata_if_missing()
    _create_player_role_snapshots_if_missing()
    _create_waiver_periods_if_missing()
    _create_waiver_processing_runs_if_missing()
    _create_player_waiver_availability_if_missing()
    _reconcile_existing_columns()


def downgrade() -> None:
    # These structures preserve historical beta data and make clean databases
    # match the upgraded schema.  Reversing them would be destructive.
    pass
