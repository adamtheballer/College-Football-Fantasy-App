"""Add durable waiver periods and complete the waiver lifecycle contract.

Revision ID: 0058_waiver_period_lifecycle
Revises: 0057_player_season_ranks
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from alembic import op
import sqlalchemy as sa


revision = "0058_waiver_period_lifecycle"
down_revision = "0057_player_season_ranks"
branch_labels = None
depends_on = None


PERIOD_STATUSES = "'scheduled', 'open', 'locked', 'processing', 'completed', 'failed'"
CLAIM_STATUSES = "'pending', 'won', 'lost', 'cancelled', 'invalid', 'insufficient_budget', 'roster_full', 'player_unavailable', 'skipped', 'failed'"
AVAILABILITY_STATES = "'waivers', 'free_agent', 'waiver_locked', 'claim_pending', 'rostered', 'game_locked'"


def _backfill_periods() -> None:
    """Create one period for every pre-0058 claim or processing run."""

    bind = op.get_bind()
    period_rows = bind.execute(
        sa.text(
            """
            SELECT league_id, season, processing_week AS week, processing_window_id AS window_key,
                   MAX(process_after) AS scheduled_for, MAX(created_at) AS created_at,
                   MAX(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) AS has_pending
            FROM waiver_claims
            GROUP BY league_id, season, processing_week, processing_window_id
            UNION
            SELECT league_id, season, week, window_key,
                   MAX(scheduled_for) AS scheduled_for, MAX(created_at) AS created_at,
                   MAX(CASE WHEN status IN ('pending', 'running') THEN 1 ELSE 0 END) AS has_pending
            FROM waiver_processing_runs
            GROUP BY league_id, season, week, window_key
            """
        )
    ).mappings()

    periods = sa.table(
        "waiver_periods",
        sa.column("id", sa.Integer),
        sa.column("league_id", sa.Integer),
        sa.column("season", sa.Integer),
        sa.column("week", sa.Integer),
        sa.column("window_key", sa.String),
        sa.column("opens_at", sa.DateTime(timezone=True)),
        sa.column("closes_at", sa.DateTime(timezone=True)),
        sa.column("processes_at", sa.DateTime(timezone=True)),
        sa.column("status", sa.String),
        sa.column("processed_at", sa.DateTime(timezone=True)),
    )
    claims = sa.table("waiver_claims", sa.column("id", sa.Integer), sa.column("waiver_period_id", sa.Integer))
    runs = sa.table("waiver_processing_runs", sa.column("id", sa.Integer), sa.column("waiver_period_id", sa.Integer))

    period_ids: dict[tuple[int, int, int, str], int] = {}
    for row in period_rows:
        key = (row["league_id"], row["season"], row["week"], row["window_key"])
        if key in period_ids:
            continue
        scheduled_for = row["scheduled_for"] or row["created_at"]
        if scheduled_for is None:
            # Pre-0058 rows always have timestamps in production. This fallback
            # keeps a damaged development database upgradeable without silently
            # assigning the period to a different week.
            scheduled_for = datetime.now(timezone.utc)
        if hasattr(scheduled_for, "tzinfo") and scheduled_for.tzinfo is None:
            scheduled_for = scheduled_for.replace(tzinfo=timezone.utc)
        opens_at = scheduled_for - timedelta(days=7) if hasattr(scheduled_for, "__sub__") else scheduled_for
        status = "scheduled" if row["has_pending"] else "completed"
        inserted = bind.execute(
            periods.insert().values(
                league_id=row["league_id"],
                season=row["season"],
                week=row["week"],
                window_key=row["window_key"],
                opens_at=opens_at,
                closes_at=scheduled_for,
                processes_at=scheduled_for,
                status=status,
                processed_at=None if status == "scheduled" else scheduled_for,
            )
        )
        period_ids[key] = int(inserted.inserted_primary_key[0])

    claim_rows = bind.execute(
        sa.text("SELECT id, league_id, season, processing_week, processing_window_id FROM waiver_claims")
    ).mappings()
    for row in claim_rows:
        bind.execute(
            claims.update()
            .where(claims.c.id == row["id"])
            .values(
                waiver_period_id=period_ids[
                    (row["league_id"], row["season"], row["processing_week"], row["processing_window_id"])
                ]
            )
        )

    run_rows = bind.execute(
        sa.text("SELECT id, league_id, season, week, window_key FROM waiver_processing_runs")
    ).mappings()
    for row in run_rows:
        bind.execute(
            runs.update()
            .where(runs.c.id == row["id"])
            .values(waiver_period_id=period_ids[(row["league_id"], row["season"], row["week"], row["window_key"])])
        )


def upgrade() -> None:
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
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint(f"status IN ({PERIOD_STATUSES})", name="ck_waiver_periods_status"),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("league_id", "season", "week", "window_key", name="uq_waiver_periods_league_window"),
    )
    op.create_index("ix_waiver_periods_due", "waiver_periods", ["processes_at", "status"])
    op.create_index("ix_waiver_periods_league_status", "waiver_periods", ["league_id", "status"])

    op.add_column("waiver_claims", sa.Column("waiver_period_id", sa.Integer(), nullable=True))
    op.add_column("waiver_processing_runs", sa.Column("waiver_period_id", sa.Integer(), nullable=True))
    op.add_column("waiver_processing_runs", sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("player_waiver_availability", sa.Column("waiver_period_id", sa.Integer(), nullable=True))
    op.add_column("league_settings", sa.Column("waivers_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column(
        "league_settings",
        sa.Column("free_agent_mode", sa.String(length=40), nullable=False, server_default="after_waivers_clear"),
    )

    _backfill_periods()

    op.alter_column("waiver_claims", "waiver_period_id", nullable=False)
    op.alter_column("waiver_processing_runs", "waiver_period_id", nullable=False)
    op.create_foreign_key(
        "fk_waiver_claims_period",
        "waiver_claims",
        "waiver_periods",
        ["waiver_period_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_waiver_processing_runs_period",
        "waiver_processing_runs",
        "waiver_periods",
        ["waiver_period_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_player_waiver_availability_period",
        "player_waiver_availability",
        "waiver_periods",
        ["waiver_period_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_unique_constraint("uq_waiver_processing_runs_period", "waiver_processing_runs", ["waiver_period_id"])

    op.drop_constraint("ck_waiver_claims_status", "waiver_claims", type_="check")
    op.create_check_constraint("ck_waiver_claims_status", "waiver_claims", f"status IN ({CLAIM_STATUSES})")
    op.drop_constraint("ck_player_waiver_availability_state", "player_waiver_availability", type_="check")
    op.execute("UPDATE player_waiver_availability SET state = 'game_locked' WHERE state = 'locked'")
    op.create_check_constraint(
        "ck_player_waiver_availability_state",
        "player_waiver_availability",
        f"state IN ({AVAILABILITY_STATES})",
    )
    op.create_check_constraint(
        "ck_league_settings_free_agent_mode",
        "league_settings",
        "free_agent_mode IN ('after_waivers_clear')",
    )

    # 0056 replaced 0052's window-wide unique constraint with partial unique
    # indexes for *pending* claims.  Replace those 0057 indexes with their
    # period-based equivalents instead of referring to the retired 0052
    # constraint, which no longer exists in an upgrade from 0057. Keep the
    # legacy window-status index because compatibility reads still expose the
    # window key and the ORM continues to declare that index.
    op.drop_index("uq_waiver_claims_pending_team_window_preference", table_name="waiver_claims")
    op.drop_index("uq_waiver_claims_pending_team_player_window", table_name="waiver_claims")
    op.drop_index("uq_waiver_claims_player_window_winner", table_name="waiver_claims")
    op.create_index("ix_waiver_claims_period_status", "waiver_claims", ["waiver_period_id", "status"])
    op.create_index(
        "uq_waiver_claims_pending_team_period_preference",
        "waiver_claims",
        ["team_id", "waiver_period_id", "preference_order"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index(
        "uq_waiver_claims_pending_team_period_player",
        "waiver_claims",
        ["team_id", "waiver_period_id", "add_player_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index(
        "uq_waiver_claims_player_period_winner",
        "waiver_claims",
        ["league_id", "add_player_id", "waiver_period_id"],
        unique=True,
        postgresql_where=sa.text("status = 'won'"),
    )


def downgrade() -> None:
    op.drop_index("uq_waiver_claims_player_period_winner", table_name="waiver_claims")
    op.drop_index("uq_waiver_claims_pending_team_period_player", table_name="waiver_claims")
    op.drop_index("uq_waiver_claims_pending_team_period_preference", table_name="waiver_claims")
    op.drop_index("ix_waiver_claims_period_status", table_name="waiver_claims")
    op.create_index(
        "uq_waiver_claims_pending_team_window_preference",
        "waiver_claims",
        ["team_id", "processing_window_id", "preference_order"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index(
        "uq_waiver_claims_pending_team_player_window",
        "waiver_claims",
        ["team_id", "add_player_id", "processing_window_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index(
        "uq_waiver_claims_player_window_winner",
        "waiver_claims",
        ["league_id", "add_player_id", "processing_window_id"],
        unique=True,
        postgresql_where=sa.text("status = 'won'"),
    )
    op.drop_constraint("ck_league_settings_free_agent_mode", "league_settings", type_="check")
    op.drop_constraint("ck_player_waiver_availability_state", "player_waiver_availability", type_="check")
    op.execute(
        "UPDATE player_waiver_availability "
        "SET state = CASE "
        "WHEN state = 'game_locked' THEN 'locked' "
        "WHEN state IN ('waiver_locked', 'claim_pending') THEN 'waivers' "
        "ELSE state END"
    )
    op.create_check_constraint(
        "ck_player_waiver_availability_state",
        "player_waiver_availability",
        "state IN ('waivers', 'free_agent', 'rostered', 'locked')",
    )
    op.drop_constraint("ck_waiver_claims_status", "waiver_claims", type_="check")
    op.execute("UPDATE waiver_claims SET status = 'invalid' WHERE status = 'skipped'")
    op.create_check_constraint(
        "ck_waiver_claims_status",
        "waiver_claims",
        "status IN ('pending', 'won', 'lost', 'cancelled', 'invalid', 'insufficient_budget', 'roster_full', 'player_unavailable', 'failed')",
    )
    op.drop_constraint("uq_waiver_processing_runs_period", "waiver_processing_runs", type_="unique")
    op.drop_constraint("fk_player_waiver_availability_period", "player_waiver_availability", type_="foreignkey")
    op.drop_constraint("fk_waiver_processing_runs_period", "waiver_processing_runs", type_="foreignkey")
    op.drop_constraint("fk_waiver_claims_period", "waiver_claims", type_="foreignkey")
    op.drop_column("league_settings", "free_agent_mode")
    op.drop_column("league_settings", "waivers_enabled")
    op.drop_column("player_waiver_availability", "waiver_period_id")
    op.drop_column("waiver_processing_runs", "failure_count")
    op.drop_column("waiver_processing_runs", "waiver_period_id")
    op.drop_column("waiver_claims", "waiver_period_id")
    op.drop_index("ix_waiver_periods_league_status", table_name="waiver_periods")
    op.drop_index("ix_waiver_periods_due", table_name="waiver_periods")
    op.drop_table("waiver_periods")
