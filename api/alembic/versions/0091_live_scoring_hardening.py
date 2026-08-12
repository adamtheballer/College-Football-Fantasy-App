"""Add append-only records and leases for the live-scoring pipeline.

Revision ID: 0091_live_scoring_hardening
Revises: 0090_expand_league_icon_url
"""

from alembic import op
import sqlalchemy as sa


revision = "0091_live_scoring_hardening"
down_revision = "0090_expand_league_icon_url"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_game_identities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_game_id", sa.String(length=128), nullable=False),
        sa.Column("game_id", sa.Integer(), sa.ForeignKey("games.id", ondelete="CASCADE"), nullable=False),
        sa.Column("verification_status", sa.String(length=30), nullable=False, server_default="unverified"),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("provider", "provider_game_id", name="uq_provider_game_identity"),
        sa.UniqueConstraint("game_id", "provider", name="uq_game_provider_identity"),
    )
    op.create_index("ix_provider_game_identities_status", "provider_game_identities", ["verification_status"])
    op.create_table(
        "provider_raw_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("feed", sa.String(length=100), nullable=False),
        sa.Column("endpoint_type", sa.String(length=100), nullable=False),
        sa.Column("provider_event_id", sa.String(length=160), nullable=False),
        sa.Column("request_key", sa.String(length=200), nullable=True),
        sa.Column("provider_revision", sa.String(length=160), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("schema_version", sa.String(length=64), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False, server_default="player_stat_revision"),
        sa.Column("season", sa.Integer(), nullable=True), sa.Column("week", sa.Integer(), nullable=True),
        sa.Column("provider_player_id", sa.String(length=128), nullable=True),
        sa.Column("provider_team_id", sa.String(length=128), nullable=True),
        sa.Column("provider_game_id", sa.String(length=128), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False), sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True), sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processing_status", sa.String(length=30), nullable=False, server_default="received"),
        sa.Column("processing_error", sa.Text(), nullable=True), sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("provider", "feed", "provider_event_id", name="uq_provider_raw_event"),
        sa.UniqueConstraint("provider", "endpoint_type", "provider_game_id", "payload_sha256", name="uq_provider_raw_payload"),
    )
    op.create_index("ix_provider_raw_events_player_game", "provider_raw_events", ["provider", "provider_player_id", "provider_game_id"])
    op.create_index("ix_provider_raw_events_received_at", "provider_raw_events", ["received_at"])
    op.create_table(
        "player_game_stat_revisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("raw_event_id", sa.Integer(), sa.ForeignKey("provider_raw_events.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("supersedes_revision_id", sa.Integer(), sa.ForeignKey("player_game_stat_revisions.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("game_id", sa.Integer(), sa.ForeignKey("games.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False), sa.Column("provider_player_id", sa.String(length=128), nullable=False),
        sa.Column("provider_game_id", sa.String(length=128), nullable=False), sa.Column("season", sa.Integer(), nullable=False), sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("provider_revision", sa.String(length=160), nullable=True),
        sa.Column("revision_number", sa.Integer(), nullable=False), sa.Column("lifecycle_state", sa.String(length=30), nullable=False),
        sa.Column("completeness", sa.String(length=30), nullable=False), sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("stats_json", sa.JSON(), nullable=False), sa.Column("missing_keys_json", sa.JSON(), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("player_id", "game_id", "revision_number", name="uq_player_game_stat_revision"),
        sa.UniqueConstraint("provider", "provider_player_id", "provider_game_id", "source_hash", name="uq_provider_stat_revision_hash"),
    )
    op.create_index("ix_player_game_stat_revisions_player_game", "player_game_stat_revisions", ["player_id", "game_id"])
    op.create_index("ix_player_game_stat_revisions_status", "player_game_stat_revisions", ["status"])
    op.create_table(
        "league_scoring_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("league_id", sa.Integer(), sa.ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False), sa.Column("rules_json", sa.JSON(), nullable=False),
        sa.Column("rules_sha256", sa.String(length=64), nullable=False), sa.Column("calculation_version", sa.String(length=64), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("league_id", "season", "rules_sha256", "calculation_version", name="uq_league_scoring_snapshot"),
    )
    op.create_index("ix_league_scoring_snapshots_league_season", "league_scoring_snapshots", ["league_id", "season"])
    op.create_table(
        "scoring_calculation_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("stat_revision_id", sa.Integer(), sa.ForeignKey("player_game_stat_revisions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("league_scoring_snapshot_id", sa.Integer(), sa.ForeignKey("league_scoring_snapshots.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("raw_event_id", sa.Integer(), sa.ForeignKey("provider_raw_events.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("league_id", sa.Integer(), sa.ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False), sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("scorer_version", sa.String(length=64), nullable=False), sa.Column("scoring_policy_hash", sa.String(length=64), nullable=False),
        sa.Column("score", sa.Float(), nullable=False), sa.Column("breakdown_json", sa.JSON(), nullable=False),
        sa.Column("publish_state", sa.String(length=30), nullable=False), sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("idempotency_key", name="uq_scoring_snapshot_idempotency"),
    )
    op.create_index("ix_scoring_snapshots_league_week", "scoring_calculation_snapshots", ["league_id", "season", "week"])
    op.create_index("ix_scoring_snapshots_revision", "scoring_calculation_snapshots", ["stat_revision_id"])
    op.create_table(
        "scoring_work_items",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("task_type", sa.String(length=80), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False), sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"), sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"), sa.Column("lease_owner", sa.String(length=120), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True), sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_category", sa.String(length=80), nullable=True), sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("idempotency_key", name="uq_scoring_work_item_idempotency"),
    )
    op.create_index("ix_scoring_work_items_ready", "scoring_work_items", ["status", "next_attempt_at"])
    op.create_index("ix_scoring_work_items_lease", "scoring_work_items", ["lease_expires_at"])
    op.create_table(
        "scoring_dead_letters",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("work_item_id", sa.Integer(), sa.ForeignKey("scoring_work_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("failure_category", sa.String(length=80), nullable=False), sa.Column("failure_message", sa.Text(), nullable=False),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=False), sa.Column("replayed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("work_item_id", name="uq_scoring_dead_letter_work_item"),
    )
    op.create_table(
        "scoring_correction_ledger",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("game_id", sa.Integer(), sa.ForeignKey("games.id", ondelete="CASCADE"), nullable=False),
        sa.Column("prior_revision_id", sa.Integer(), sa.ForeignKey("player_game_stat_revisions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("corrected_revision_id", sa.Integer(), sa.ForeignKey("player_game_stat_revisions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("raw_event_id", sa.Integer(), sa.ForeignKey("provider_raw_events.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False), sa.Column("impact_json", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_scoring_correction_ledger_player_game", "scoring_correction_ledger", ["player_id", "game_id"])


def downgrade() -> None:
    for table in ("scoring_correction_ledger", "scoring_dead_letters", "scoring_work_items", "scoring_calculation_snapshots", "league_scoring_snapshots", "player_game_stat_revisions", "provider_raw_events", "provider_game_identities"):
        op.drop_table(table)
