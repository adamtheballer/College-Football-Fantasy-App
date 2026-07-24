"""Create durable unified FAAB and priority waiver state."""

from alembic import op
import sqlalchemy as sa


revision = "0052_unified_waiver_config"
down_revision = "0051_auth_version"
branch_labels = None
depends_on = None


CLAIM_STATUSES = "'pending', 'won', 'lost', 'cancelled', 'invalid', 'insufficient_budget', 'roster_full', 'player_unavailable', 'failed'"


def upgrade() -> None:
    op.execute("UPDATE league_settings SET waiver_type = lower(waiver_type)")
    op.execute("UPDATE league_settings SET waiver_type = 'priority' WHERE waiver_type IN ('rolling', 'reverse')")
    op.execute("UPDATE league_settings SET waiver_type = 'faab' WHERE waiver_type = 'continuous_faab'")
    unsupported = op.get_bind().execute(sa.text("SELECT count(*) FROM league_settings WHERE waiver_type NOT IN ('faab', 'priority')")).scalar_one()
    if unsupported:
        raise RuntimeError("Cannot migrate unsupported legacy waiver types; resolve affected league_settings rows first.")

    with op.batch_alter_table("league_settings") as batch:
        batch.alter_column("waiver_process_day", new_column_name="waiver_processing_weekday", existing_type=sa.Integer())
        batch.alter_column("waiver_process_hour", new_column_name="waiver_processing_hour", existing_type=sa.Integer())
        batch.alter_column("faab_budget", new_column_name="faab_starting_budget", existing_type=sa.Integer())
        batch.alter_column("allow_zero_dollar_bids", new_column_name="allow_zero_faab_bids", existing_type=sa.Boolean())
        batch.add_column(sa.Column("waiver_timezone", sa.String(length=64), nullable=False, server_default="America/New_York"))
        batch.add_column(sa.Column("waiver_initialized_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_check_constraint("ck_league_settings_waiver_type", "waiver_type IN ('faab', 'priority')")
        batch.create_check_constraint("ck_league_settings_faab_starting_budget", "faab_starting_budget >= 0")
        batch.create_check_constraint("ck_league_settings_waiver_processing_weekday", "waiver_processing_weekday BETWEEN 0 AND 6")
        batch.create_check_constraint("ck_league_settings_waiver_processing_hour", "waiver_processing_hour BETWEEN 0 AND 23")
        batch.create_check_constraint("ck_league_settings_post_drop_waiver_hours", "post_drop_waiver_hours >= 0")

    # Tuesday (Python weekday 1) at 8:00 AM is the canonical weekly waiver opening.
    # This migration has not been applied to the canonical database yet, so existing
    # legacy settings are intentionally aligned with the new product-wide schedule.
    op.execute("UPDATE league_settings SET waiver_processing_weekday = 1, waiver_processing_hour = 8")
    op.alter_column("league_settings", "waiver_processing_weekday", server_default="1")
    op.alter_column("league_settings", "waiver_processing_hour", server_default="8")

    op.execute("UPDATE waiver_claims SET status = 'won' WHERE status = 'processed'")
    op.add_column("waiver_claims", sa.Column("season", sa.Integer(), nullable=True))
    op.add_column("waiver_claims", sa.Column("processing_week", sa.Integer(), nullable=True))
    op.add_column("waiver_claims", sa.Column("processing_window_id", sa.String(length=120), nullable=True))
    op.add_column("waiver_claims", sa.Column("processing_run_id", sa.Integer(), nullable=True))
    op.add_column("waiver_claims", sa.Column("preference_order", sa.Integer(), nullable=True))
    op.add_column("waiver_claims", sa.Column("winning_bid", sa.Integer(), nullable=True))
    op.add_column("waiver_claims", sa.Column("prior_priority", sa.Integer(), nullable=True))
    op.add_column("waiver_claims", sa.Column("resulting_priority", sa.Integer(), nullable=True))
    op.add_column("waiver_claims", sa.Column("failure_code", sa.String(length=80), nullable=True))
    op.execute("UPDATE waiver_claims c SET season = l.season_year FROM leagues l WHERE c.league_id = l.id")
    op.execute("UPDATE waiver_claims SET processing_week = 0 WHERE processing_week IS NULL")
    op.execute("UPDATE waiver_claims SET processing_window_id = 'legacy:' || id::text WHERE processing_window_id IS NULL")
    # 0051 stores the prior per-team ordering snapshot as priority_snapshot.
    # There is no claim_priority column in the deployed 0051 schema.
    op.execute("UPDATE waiver_claims SET preference_order = COALESCE(priority_snapshot, 1) WHERE preference_order IS NULL")
    op.alter_column("waiver_claims", "season", nullable=False)
    op.alter_column("waiver_claims", "processing_week", nullable=False)
    op.alter_column("waiver_claims", "processing_window_id", nullable=False)
    op.alter_column("waiver_claims", "preference_order", nullable=False)
    op.create_check_constraint("ck_waiver_claims_faab_bid_nonnegative", "waiver_claims", "faab_bid >= 0")
    op.create_check_constraint("ck_waiver_claims_preference_order_positive", "waiver_claims", "preference_order > 0")
    op.create_check_constraint("ck_waiver_claims_status", "waiver_claims", f"status IN ({CLAIM_STATUSES})")
    op.create_unique_constraint("uq_waiver_claims_team_window_preference", "waiver_claims", ["team_id", "processing_window_id", "preference_order"])
    op.create_index("ix_waiver_claims_window_status", "waiver_claims", ["league_id", "processing_window_id", "status"])
    op.create_index("uq_waiver_claims_player_window_winner", "waiver_claims", ["league_id", "add_player_id", "processing_window_id"], unique=True, postgresql_where=sa.text("status = 'won'"))

    op.create_table(
        "waiver_processing_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("league_id", sa.Integer(), sa.ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("window_key", sa.String(length=120), nullable=False),
        sa.Column("waiver_type", sa.String(length=20), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("claims_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("claims_won", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("waiver_type IN ('faab', 'priority')", name="ck_waiver_processing_runs_waiver_type"),
        sa.CheckConstraint("status IN ('pending', 'running', 'completed', 'failed')", name="ck_waiver_processing_runs_status"),
        sa.UniqueConstraint("league_id", "season", "week", "window_key", name="uq_waiver_processing_runs_window"),
        sa.UniqueConstraint("idempotency_key", name="uq_waiver_processing_runs_idempotency_key"),
    )
    op.create_index("ix_waiver_processing_runs_due", "waiver_processing_runs", ["scheduled_for", "status"])
    op.create_foreign_key("fk_waiver_claims_processing_run", "waiver_claims", "waiver_processing_runs", ["processing_run_id"], ["id"], ondelete="SET NULL")
    op.create_table(
        "player_waiver_availability",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("league_id", sa.Integer(), sa.ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False, server_default="waivers"),
        sa.Column("available_at", sa.DateTime(timezone=True)),
        sa.Column("locked_at", sa.DateTime(timezone=True)),
        sa.Column("source_transaction_id", sa.Integer(), sa.ForeignKey("transactions.id", ondelete="SET NULL")),
        sa.Column("dropped_by_team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("state IN ('waivers', 'free_agent', 'rostered', 'locked')", name="ck_player_waiver_availability_state"),
        sa.UniqueConstraint("league_id", "player_id", name="uq_player_waiver_availability_league_player"),
    )
    op.create_index("ix_player_waiver_availability_due", "player_waiver_availability", ["league_id", "state", "available_at"])

    with op.batch_alter_table("waiver_priorities") as batch:
        batch.create_unique_constraint("uq_waiver_priorities_league_priority", ["league_id", "priority"])
        batch.create_check_constraint("ck_waiver_priorities_priority_positive", "priority > 0")
        batch.create_check_constraint("ck_waiver_priorities_faab_budget_nonnegative", "faab_budget >= 0")
        batch.create_check_constraint("ck_waiver_priorities_faab_spent_nonnegative", "faab_spent >= 0")
        batch.create_check_constraint("ck_waiver_priorities_faab_remaining_nonnegative", "faab_spent <= faab_budget")


def downgrade() -> None:
    with op.batch_alter_table("waiver_priorities") as batch:
        batch.drop_constraint("ck_waiver_priorities_faab_remaining_nonnegative", type_="check")
        batch.drop_constraint("ck_waiver_priorities_faab_spent_nonnegative", type_="check")
        batch.drop_constraint("ck_waiver_priorities_faab_budget_nonnegative", type_="check")
        batch.drop_constraint("ck_waiver_priorities_priority_positive", type_="check")
        batch.drop_constraint("uq_waiver_priorities_league_priority", type_="unique")
    op.drop_index("ix_player_waiver_availability_due", table_name="player_waiver_availability")
    op.drop_table("player_waiver_availability")
    op.drop_index("uq_waiver_claims_player_window_winner", table_name="waiver_claims")
    op.drop_index("ix_waiver_claims_window_status", table_name="waiver_claims")
    op.drop_constraint("uq_waiver_claims_team_window_preference", "waiver_claims", type_="unique")
    op.drop_constraint("ck_waiver_claims_status", "waiver_claims", type_="check")
    op.drop_constraint("ck_waiver_claims_preference_order_positive", "waiver_claims", type_="check")
    op.drop_constraint("ck_waiver_claims_faab_bid_nonnegative", "waiver_claims", type_="check")
    op.drop_constraint("fk_waiver_claims_processing_run", "waiver_claims", type_="foreignkey")
    for column in ("failure_code", "resulting_priority", "prior_priority", "winning_bid", "preference_order", "processing_run_id", "processing_window_id", "processing_week", "season"):
        op.drop_column("waiver_claims", column)
    op.drop_index("ix_waiver_processing_runs_due", table_name="waiver_processing_runs")
    op.drop_table("waiver_processing_runs")
    with op.batch_alter_table("league_settings") as batch:
        for constraint in ("ck_league_settings_post_drop_waiver_hours", "ck_league_settings_waiver_processing_hour", "ck_league_settings_waiver_processing_weekday", "ck_league_settings_faab_starting_budget", "ck_league_settings_waiver_type"):
            batch.drop_constraint(constraint, type_="check")
        batch.drop_column("waiver_initialized_at")
        batch.drop_column("waiver_timezone")
        batch.alter_column("allow_zero_faab_bids", new_column_name="allow_zero_dollar_bids", existing_type=sa.Boolean())
        batch.alter_column("faab_starting_budget", new_column_name="faab_budget", existing_type=sa.Integer())
        batch.alter_column("waiver_processing_hour", new_column_name="waiver_process_hour", existing_type=sa.Integer())
        batch.alter_column("waiver_processing_weekday", new_column_name="waiver_process_day", existing_type=sa.Integer())
