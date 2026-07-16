"""Reconcile head-stamped legacy databases with the canonical application schema.

Revision ID: 0040_reconcile_active_schema
Revises: 0039_archive_retired_schema
Create Date: 2026-07-15 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0040_reconcile_active_schema"
down_revision: str | None = "0039_archive_retired_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _indexes(table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _unique_constraints(table_name: str) -> set[str]:
    return {
        constraint["name"]
        for constraint in sa.inspect(op.get_bind()).get_unique_constraints(table_name)
        if constraint["name"] is not None
    }


def _create_missing_lifecycle_tables() -> None:
    tables = _tables()
    if "college_teams" not in tables:
        op.create_table(
            "college_teams",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("conference", sa.String(50), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name", name="uq_college_teams_name"),
        )
        op.create_index("ix_college_teams_conference", "college_teams", ["conference"])

    if "mock_drafts" not in tables:
        op.create_table(
            "mock_drafts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("owner_user_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(120), nullable=False),
            sa.Column("status", sa.String(30), nullable=False),
            sa.Column("league_size", sa.Integer(), nullable=False),
            sa.Column("rounds", sa.Integer(), nullable=False),
            sa.Column("current_pick", sa.Integer(), nullable=False),
            sa.Column("settings_json", sa.JSON(), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_mock_drafts_owner_user_id", "mock_drafts", ["owner_user_id"])
        op.create_index("ix_mock_drafts_status", "mock_drafts", ["status"])

    if "player_provider_ids" not in tables:
        op.create_table(
            "player_provider_ids",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("player_id", sa.Integer(), nullable=False),
            sa.Column("provider", sa.String(64), nullable=False),
            sa.Column("provider_player_id", sa.String(128), nullable=False),
            sa.Column("provider_team_id", sa.String(128), nullable=True),
            sa.Column("match_confidence", sa.Float(), nullable=True),
            sa.Column("verification_status", sa.String(30), nullable=False),
            sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("verified_by_user_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["verified_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("player_id", "provider", name="uq_player_provider_ids_player_provider"),
            sa.UniqueConstraint("provider", "provider_player_id", name="uq_player_provider_ids_provider_player"),
        )
        op.create_index("ix_player_provider_ids_player_id", "player_provider_ids", ["player_id"])
        op.create_index("ix_player_provider_ids_provider", "player_provider_ids", ["provider"])
        op.create_index("ix_player_provider_ids_verification_status", "player_provider_ids", ["verification_status"])

    if "team_provider_ids" not in tables:
        op.create_table(
            "team_provider_ids",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("team_id", sa.Integer(), nullable=False),
            sa.Column("provider", sa.String(64), nullable=False),
            sa.Column("provider_team_id", sa.String(128), nullable=False),
            sa.Column("provider_team_name", sa.String(200), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["team_id"], ["college_teams.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("provider", "provider_team_id", name="uq_team_provider_ids_provider_team"),
            sa.UniqueConstraint("team_id", "provider", name="uq_team_provider_ids_team_provider"),
        )
        op.create_index("ix_team_provider_ids_team_id", "team_provider_ids", ["team_id"])
        op.create_index("ix_team_provider_ids_provider", "team_provider_ids", ["provider"])

    if "unmatched_provider_rows" not in tables:
        op.create_table(
            "unmatched_provider_rows",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("provider", sa.String(64), nullable=False),
            sa.Column("feed", sa.String(100), nullable=False),
            sa.Column("season", sa.Integer(), nullable=True),
            sa.Column("week", sa.Integer(), nullable=True),
            sa.Column("provider_player_id", sa.String(128), nullable=True),
            sa.Column("provider_team_id", sa.String(128), nullable=True),
            sa.Column("player_name", sa.String(200), nullable=True),
            sa.Column("team_name", sa.String(200), nullable=True),
            sa.Column("dedupe_hash", sa.String(64), nullable=False),
            sa.Column("raw_payload", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(30), nullable=False),
            sa.Column("occurrence_count", sa.Integer(), nullable=False),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("resolved_by_user_id", sa.Integer(), nullable=True),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("mapped_player_id", sa.Integer(), nullable=True),
            sa.Column("notes", sa.String(1000), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["mapped_player_id"], ["players.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["resolved_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("provider", "feed", "dedupe_hash", name="uq_unmatched_provider_rows_provider_feed_hash"),
        )
        op.create_index("ix_unmatched_provider_rows_status", "unmatched_provider_rows", ["status"])
        op.create_index("ix_unmatched_provider_rows_provider_feed", "unmatched_provider_rows", ["provider", "feed"])
        op.create_index("ix_unmatched_provider_rows_provider_player_id", "unmatched_provider_rows", ["provider_player_id"])
        op.create_index("ix_unmatched_provider_rows_provider_team_id", "unmatched_provider_rows", ["provider_team_id"])

    if "provider_identity_audits" not in tables:
        op.create_table(
            "provider_identity_audits",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("entity_type", sa.String(50), nullable=False),
            sa.Column("entity_id", sa.Integer(), nullable=True),
            sa.Column("action", sa.String(50), nullable=False),
            sa.Column("provider", sa.String(64), nullable=True),
            sa.Column("provider_player_id", sa.String(128), nullable=True),
            sa.Column("provider_team_id", sa.String(128), nullable=True),
            sa.Column("unmatched_row_id", sa.Integer(), nullable=True),
            sa.Column("actor_user_id", sa.Integer(), nullable=True),
            sa.Column("before_state", sa.JSON(), nullable=True),
            sa.Column("after_state", sa.JSON(), nullable=True),
            sa.Column("reason", sa.String(1000), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["unmatched_row_id"], ["unmatched_provider_rows.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_provider_identity_audits_entity", "provider_identity_audits", ["entity_type", "entity_id"])
        op.create_index("ix_provider_identity_audits_provider", "provider_identity_audits", ["provider"])
        op.create_index("ix_provider_identity_audits_actor_user_id", "provider_identity_audits", ["actor_user_id"])

    if "league_messages" not in tables:
        op.create_table(
            "league_messages",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("league_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("message_type", sa.String(50), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_league_messages_league_id", "league_messages", ["league_id"])
        op.create_index("ix_league_messages_message_type", "league_messages", ["message_type"])

    if "player_week_scores" not in tables:
        op.create_table(
            "player_week_scores",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("league_id", sa.Integer(), nullable=False),
            sa.Column("player_id", sa.Integer(), nullable=False),
            sa.Column("season", sa.Integer(), nullable=False),
            sa.Column("week", sa.Integer(), nullable=False),
            sa.Column("fantasy_points", sa.Float(), nullable=False),
            sa.Column("status", sa.String(50), nullable=False),
            sa.Column("breakdown_json", sa.JSON(), nullable=False),
            sa.Column("source_stat_id", sa.Integer(), nullable=True),
            sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["source_stat_id"], ["player_stats.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("league_id", "player_id", "season", "week", name="uq_player_week_scores_league_player_week"),
        )
        op.create_index("ix_player_week_scores_league_week", "player_week_scores", ["league_id", "season", "week"])
        op.create_index("ix_player_week_scores_player_id", "player_week_scores", ["player_id"])
        op.create_index("ix_player_week_scores_status", "player_week_scores", ["status"])

    if "scoring_admin_audits" not in tables:
        op.create_table(
            "scoring_admin_audits",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("action", sa.String(80), nullable=False),
            sa.Column("actor_user_id", sa.Integer(), nullable=True),
            sa.Column("league_id", sa.Integer(), nullable=True),
            sa.Column("season", sa.Integer(), nullable=True),
            sa.Column("week", sa.Integer(), nullable=True),
            sa.Column("player_id", sa.Integer(), nullable=True),
            sa.Column("affected_league_ids", sa.JSON(), nullable=True),
            sa.Column("reason", sa.String(1000), nullable=False),
            sa.Column("before_state", sa.JSON(), nullable=True),
            sa.Column("after_state", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_scoring_admin_audits_action", "scoring_admin_audits", ["action"])
        op.create_index("ix_scoring_admin_audits_actor_user_id", "scoring_admin_audits", ["actor_user_id"])
        op.create_index("ix_scoring_admin_audits_league_week", "scoring_admin_audits", ["league_id", "season", "week"])
        op.create_index("ix_scoring_admin_audits_player_week", "scoring_admin_audits", ["player_id", "season", "week"])

    if "waiver_priorities" not in tables:
        op.create_table(
            "waiver_priorities",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("league_id", sa.Integer(), nullable=False),
            sa.Column("team_id", sa.Integer(), nullable=False),
            sa.Column("priority", sa.Integer(), nullable=False),
            sa.Column("faab_budget", sa.Integer(), nullable=False),
            sa.Column("faab_spent", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("league_id", "team_id", name="uq_waiver_priorities_league_team"),
        )
        op.create_index("ix_waiver_priorities_league_priority", "waiver_priorities", ["league_id", "priority"])

    if "trade_reviews" not in tables:
        op.create_table(
            "trade_reviews",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("trade_offer_id", sa.Integer(), nullable=False),
            sa.Column("reviewer_user_id", sa.Integer(), nullable=True),
            sa.Column("action", sa.String(50), nullable=False),
            sa.Column("reason", sa.String(1000), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["trade_offer_id"], ["trade_offers.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_trade_reviews_action", "trade_reviews", ["action"])
        op.create_index("ix_trade_reviews_reviewer_user_id", "trade_reviews", ["reviewer_user_id"])
        op.create_index("ix_trade_reviews_trade_offer_id", "trade_reviews", ["trade_offer_id"])

    if "waiver_claim_audits" not in tables:
        op.create_table(
            "waiver_claim_audits",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("waiver_claim_id", sa.Integer(), nullable=False),
            sa.Column("league_id", sa.Integer(), nullable=False),
            sa.Column("team_id", sa.Integer(), nullable=False),
            sa.Column("action", sa.String(40), nullable=False),
            sa.Column("actor_user_id", sa.Integer(), nullable=True),
            sa.Column("reason", sa.String(500), nullable=True),
            sa.Column("before_state", sa.JSON(), nullable=True),
            sa.Column("after_state", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["waiver_claim_id"], ["waiver_claims.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_waiver_claim_audits_action", "waiver_claim_audits", ["action"])
        op.create_index("ix_waiver_claim_audits_claim_id", "waiver_claim_audits", ["waiver_claim_id"])


def _rebuild_legacy_mock_draft_picks() -> None:
    tables = _tables()
    if "mock_draft_picks" not in tables or "legacy_archive_mock_draft_picks" in tables:
        return
    if {"session_id", "overall_pick"}.isdisjoint(_columns("mock_draft_picks")):
        return

    op.rename_table("mock_draft_picks", "legacy_archive_mock_draft_picks")
    for index_name in ("ix_mock_draft_picks_mock_draft_id", "ix_mock_draft_picks_player_id"):
        if index_name in _indexes("legacy_archive_mock_draft_picks"):
            op.drop_index(index_name, table_name="legacy_archive_mock_draft_picks")
    op.create_table(
        "mock_draft_picks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("mock_draft_id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("pick_number", sa.Integer(), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("round_pick", sa.Integer(), nullable=False),
        sa.Column("team_index", sa.Integer(), nullable=False),
        sa.Column("team_name", sa.String(120), nullable=False),
        sa.Column("player_name", sa.String(200), nullable=False),
        sa.Column("player_school", sa.String(200), nullable=False),
        sa.Column("player_position", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["mock_draft_id"], ["mock_drafts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mock_draft_id", "pick_number", name="uq_mock_draft_picks_mock_pick_number"),
        sa.UniqueConstraint("mock_draft_id", "player_id", name="uq_mock_draft_picks_mock_player"),
    )
    op.create_index("ix_mock_draft_picks_mock_draft_id", "mock_draft_picks", ["mock_draft_id"])
    op.create_index("ix_mock_draft_picks_player_id", "mock_draft_picks", ["player_id"])


def _add_column(table_name: str, column: sa.Column) -> None:
    if column.name not in _columns(table_name):
        op.add_column(table_name, column)


def _reconcile_scoring_tables() -> None:
    if "scoring_runs" in _tables():
        _add_column("scoring_runs", sa.Column("provider", sa.String(50), nullable=True))
        _add_column("scoring_runs", sa.Column("players_updated", sa.Integer(), nullable=True))
        _add_column("scoring_runs", sa.Column("teams_updated", sa.Integer(), nullable=True))
        _add_column("scoring_runs", sa.Column("matchups_updated", sa.Integer(), nullable=True))
        _add_column("scoring_runs", sa.Column("error_message", sa.String(1000), nullable=True))
        op.execute("UPDATE scoring_runs SET provider = COALESCE(provider, 'sportsdata'), players_updated = COALESCE(players_updated, 0), teams_updated = COALESCE(teams_updated, 0), matchups_updated = COALESCE(matchups_updated, 0)")
        with op.batch_alter_table("scoring_runs") as batch:
            batch.alter_column("league_id", existing_type=sa.Integer(), nullable=True)
            batch.alter_column("status", existing_type=sa.String(20), type_=sa.String(50))
            batch.alter_column("provider", existing_type=sa.String(50), nullable=False)
            batch.alter_column("players_updated", existing_type=sa.Integer(), nullable=False)
            batch.alter_column("teams_updated", existing_type=sa.Integer(), nullable=False)
            batch.alter_column("matchups_updated", existing_type=sa.Integer(), nullable=False)
        for column in ("source_mode", "finalized_week_state", "note", "finalize_matchups", "created_by_user_id"):
            if column in _columns("scoring_runs"):
                op.drop_column("scoring_runs", column)
        for index in ("ix_scoring_runs_created_at",):
            if index in _indexes("scoring_runs"):
                op.drop_index(index, table_name="scoring_runs")
        op.execute("ALTER TABLE scoring_runs DROP CONSTRAINT IF EXISTS scoring_runs_created_by_user_id_fkey")

    if "team_week_scores" in _tables():
        _add_column("team_week_scores", sa.Column("points_total", sa.Float(), nullable=True))
        _add_column("team_week_scores", sa.Column("points_starters", sa.Float(), nullable=True))
        _add_column("team_week_scores", sa.Column("points_bench", sa.Float(), nullable=True))
        _add_column("team_week_scores", sa.Column("starter_points", sa.Float(), nullable=True))
        _add_column("team_week_scores", sa.Column("bench_points", sa.Float(), nullable=True))
        _add_column("team_week_scores", sa.Column("total_points", sa.Float(), nullable=True))
        _add_column("team_week_scores", sa.Column("breakdown_json", sa.JSON(), nullable=True))
        _add_column("team_week_scores", sa.Column("status", sa.String(50), nullable=True))
        _add_column("team_week_scores", sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=True))
        op.execute("UPDATE team_week_scores SET points_total = COALESCE(points_total, total_points, 0), points_starters = COALESCE(points_starters, starter_points, 0), points_bench = COALESCE(points_bench, bench_points, 0), starter_points = COALESCE(starter_points, points_starters, 0), bench_points = COALESCE(bench_points, points_bench, 0), total_points = COALESCE(total_points, points_total, 0), breakdown_json = COALESCE(breakdown_json, '{}'::json), status = COALESCE(status, 'live')")
        with op.batch_alter_table("team_week_scores") as batch:
            batch.alter_column("points_total", existing_type=sa.Float(), nullable=False)
            batch.alter_column("points_starters", existing_type=sa.Float(), nullable=False)
            batch.alter_column("points_bench", existing_type=sa.Float(), nullable=False)
            batch.alter_column("starter_points", existing_type=sa.Float(), nullable=False)
            batch.alter_column("bench_points", existing_type=sa.Float(), nullable=False)
            batch.alter_column("total_points", existing_type=sa.Float(), nullable=False)
            batch.alter_column("breakdown_json", existing_type=sa.JSON(), nullable=False)
            batch.alter_column("status", existing_type=sa.String(50), nullable=False)
            if "uq_team_week_scores_league_team_week" not in _unique_constraints("team_week_scores"):
                batch.create_unique_constraint("uq_team_week_scores_league_team_week", ["league_id", "team_id", "season", "week"])


def _reconcile_trade_tables() -> None:
    if "trade_offers" not in _tables():
        return

    _add_column("trade_offers", sa.Column("proposing_team_id", sa.Integer(), nullable=True))
    _add_column("trade_offers", sa.Column("receiving_team_id", sa.Integer(), nullable=True))
    _add_column("trade_offers", sa.Column("created_by_user_id", sa.Integer(), nullable=True))
    _add_column("trade_offers", sa.Column("message", sa.String(1000), nullable=True))
    _add_column("trade_offers", sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True))
    _add_column("trade_offers", sa.Column("process_after", sa.DateTime(timezone=True), nullable=True))
    _add_column("trade_offers", sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True))
    _add_column("trade_offers", sa.Column("failure_reason", sa.String(1000), nullable=True))
    legacy_offer_columns = _columns("trade_offers")
    if {"from_team_id", "to_team_id", "from_user_id", "note", "responded_at"}.intersection(legacy_offer_columns):
        op.execute(
            """
            UPDATE trade_offers
            SET proposing_team_id = COALESCE(proposing_team_id, from_team_id),
                receiving_team_id = COALESCE(receiving_team_id, to_team_id),
                created_by_user_id = COALESCE(created_by_user_id, from_user_id),
                message = COALESCE(message, note),
                accepted_at = COALESCE(accepted_at, responded_at)
            """
        )
    with op.batch_alter_table("trade_offers") as batch:
        batch.alter_column("proposing_team_id", existing_type=sa.Integer(), nullable=False)
        batch.alter_column("receiving_team_id", existing_type=sa.Integer(), nullable=False)
        batch.alter_column("status", existing_type=sa.String(30), type_=sa.String(50))
    for index in ("ix_trade_offers_expires_at", "ix_trade_offers_from_team_id", "ix_trade_offers_to_team_id"):
        if index in _indexes("trade_offers"):
            op.drop_index(index, table_name="trade_offers")
    for index, columns in (
        ("ix_trade_offers_process_after", ["process_after"]),
        ("ix_trade_offers_proposing_team_id", ["proposing_team_id"]),
        ("ix_trade_offers_receiving_team_id", ["receiving_team_id"]),
    ):
        if index not in _indexes("trade_offers"):
            op.create_index(index, "trade_offers", columns)
    for constraint in (
        "trade_offers_from_user_id_fkey",
        "trade_offers_from_team_id_fkey",
        "trade_offers_to_user_id_fkey",
        "trade_offers_to_team_id_fkey",
        "uq_trade_offers_proposal_ref",
    ):
        op.execute(f"ALTER TABLE trade_offers DROP CONSTRAINT IF EXISTS {constraint}")
    op.execute("ALTER TABLE trade_offers DROP CONSTRAINT IF EXISTS trade_offers_proposing_team_id_fkey")
    op.execute("ALTER TABLE trade_offers DROP CONSTRAINT IF EXISTS trade_offers_receiving_team_id_fkey")
    op.execute("ALTER TABLE trade_offers DROP CONSTRAINT IF EXISTS trade_offers_created_by_user_id_fkey")
    op.create_foreign_key(None, "trade_offers", "teams", ["proposing_team_id"], ["id"], ondelete="CASCADE")
    op.create_foreign_key(None, "trade_offers", "teams", ["receiving_team_id"], ["id"], ondelete="CASCADE")
    op.create_foreign_key(None, "trade_offers", "users", ["created_by_user_id"], ["id"], ondelete="SET NULL")
    for column in (
        "from_team_id",
        "to_team_id",
        "from_user_id",
        "to_user_id",
        "note",
        "proposal_ref",
        "responded_at",
        "review_mode",
        "review_status",
    ):
        if column in _columns("trade_offers"):
            op.drop_column("trade_offers", column)

    if "trade_offer_items" not in _tables():
        return
    _add_column("trade_offer_items", sa.Column("team_id", sa.Integer(), nullable=True))
    _add_column("trade_offer_items", sa.Column("draft_pick_id", sa.Integer(), nullable=True))
    _add_column("trade_offer_items", sa.Column("item_type", sa.String(30), nullable=True))
    if "side" in _columns("trade_offer_items"):
        op.execute(
            """
            UPDATE trade_offer_items item
            SET team_id = COALESCE(
                    item.team_id,
                    CASE WHEN item.side IN ('give', 'from', 'proposing')
                         THEN offer.proposing_team_id ELSE offer.receiving_team_id END
                ),
                item_type = COALESCE(item.item_type, 'player')
            FROM trade_offers offer
            WHERE offer.id = item.trade_offer_id
            """
        )
    with op.batch_alter_table("trade_offer_items") as batch:
        batch.alter_column("team_id", existing_type=sa.Integer(), nullable=False)
        batch.alter_column("item_type", existing_type=sa.String(30), nullable=False)
        batch.alter_column("player_id", existing_type=sa.Integer(), nullable=True)
    op.execute("ALTER TABLE trade_offer_items DROP CONSTRAINT IF EXISTS trade_offer_items_player_id_fkey")
    op.execute("ALTER TABLE trade_offer_items DROP CONSTRAINT IF EXISTS trade_offer_items_team_id_fkey")
    op.execute("ALTER TABLE trade_offer_items DROP CONSTRAINT IF EXISTS trade_offer_items_draft_pick_id_fkey")
    op.create_foreign_key(None, "trade_offer_items", "players", ["player_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key(None, "trade_offer_items", "teams", ["team_id"], ["id"], ondelete="CASCADE")
    op.create_foreign_key(None, "trade_offer_items", "draft_picks", ["draft_pick_id"], ["id"], ondelete="SET NULL")
    if "ix_trade_offer_items_team_id" not in _indexes("trade_offer_items"):
        op.create_index("ix_trade_offer_items_team_id", "trade_offer_items", ["team_id"])
    if "side" in _columns("trade_offer_items"):
        op.drop_column("trade_offer_items", "side")


def _reconcile_waiver_tables() -> None:
    if "waiver_claims" not in _tables():
        return
    _add_column("waiver_claims", sa.Column("drop_roster_entry_id", sa.Integer(), nullable=True))
    _add_column("waiver_claims", sa.Column("faab_bid", sa.Integer(), nullable=True))
    _add_column("waiver_claims", sa.Column("process_after", sa.DateTime(timezone=True), nullable=True))
    _add_column("waiver_claims", sa.Column("failure_reason", sa.String(500), nullable=True))
    legacy_claim_columns = _columns("waiver_claims")
    if {"bid_amount", "processed_reason"}.intersection(legacy_claim_columns):
        op.execute(
            """
            UPDATE waiver_claims
            SET faab_bid = COALESCE(faab_bid, bid_amount, 0),
                process_after = COALESCE(process_after, created_at),
                failure_reason = COALESCE(failure_reason, processed_reason)
            """
        )
    with op.batch_alter_table("waiver_claims") as batch:
        batch.alter_column("faab_bid", existing_type=sa.Integer(), nullable=False)
        batch.alter_column("status", existing_type=sa.String(20), type_=sa.String(30))
    for index in (
        "ix_waiver_claims_add_player_id",
        "ix_waiver_claims_league_id_created_at",
        "ix_waiver_claims_league_id_status",
        "ix_waiver_claims_team_id_status",
    ):
        if index in _indexes("waiver_claims"):
            op.drop_index(index, table_name="waiver_claims")
    for index, columns in (
        ("ix_waiver_claims_add_player", ["league_id", "add_player_id"]),
        ("ix_waiver_claims_league_status", ["league_id", "status"]),
        ("ix_waiver_claims_process_after", ["process_after"]),
        ("ix_waiver_claims_team_status", ["team_id", "status"]),
    ):
        if index not in _indexes("waiver_claims"):
            op.create_index(index, "waiver_claims", columns)
    for column in ("bid_amount", "note", "process_batch_key", "processed_reason"):
        if column in _columns("waiver_claims"):
            op.drop_column("waiver_claims", column)


def _remove_retired_columns_and_indexes() -> None:
    for table_name, columns in {
        "teams": ("faab_balance", "waiver_priority"),
        "league_settings": ("waiver_mode", "weekly_waiver_day"),
        "league_invites": ("email_domain", "expires_at", "max_uses", "revoked_at", "uses_count"),
        "drafts": (
            "autopick_strategy",
            "clock_seconds",
            "current_pick_expires_at",
            "history_email_sent_at",
            "pause_accumulated_seconds",
            "paused_at",
            "pick_expires_at",
            "pick_started_at",
        ),
        "draft_picks": ("idempotency_key",),
    }.items():
        if table_name not in _tables():
            continue
        for column in columns:
            if column in _columns(table_name):
                op.drop_column(table_name, column)

    for table_name, indexes in {
        "roster_entries": ("ix_roster_entries_team_status",),
        "teams": ("ix_teams_owner_user_id",),
        "weekly_projections": ("ix_weekly_projections_season_week_player", "ix_weekly_projections_season_week_points"),
        "games": ("ix_games_season_week_home", "ix_games_season_week_away"),
        "injuries": ("ix_injuries_season_week_status",),
        "leagues": ("ix_leagues_status",),
        "drafts": ("ix_drafts_live_state",),
        "draft_picks": ("ix_draft_picks_draft_id_idempotency_key",),
    }.items():
        if table_name not in _tables():
            continue
        for index in indexes:
            if index in _indexes(table_name):
                op.drop_index(index, table_name=table_name)

    op.execute("ALTER TABLE auth_action_tokens DROP CONSTRAINT IF EXISTS auth_action_tokens_token_hash_key")
    op.execute("ALTER TABLE drafts DROP CONSTRAINT IF EXISTS uq_drafts_league_id")
    op.execute("ALTER TABLE draft_picks DROP CONSTRAINT IF EXISTS uq_draft_picks_draft_id_idempotency_key")


def _align_remaining_types() -> None:
    if "push_tokens" in _tables():
        with op.batch_alter_table("push_tokens") as batch:
            batch.alter_column("device_token", existing_type=sa.Text(), type_=sa.String(255))
    if "lineup_week_snapshots" in _tables():
        with op.batch_alter_table("lineup_week_snapshots") as batch:
            batch.alter_column("created_at", existing_type=sa.DateTime(timezone=True), nullable=False)
            batch.alter_column("updated_at", existing_type=sa.DateTime(timezone=True), nullable=False)


def upgrade() -> None:
    _create_missing_lifecycle_tables()
    _rebuild_legacy_mock_draft_picks()
    _reconcile_scoring_tables()
    _reconcile_trade_tables()
    _reconcile_waiver_tables()
    _remove_retired_columns_and_indexes()
    _align_remaining_types()


def downgrade() -> None:
    raise NotImplementedError("Schema reconciliation is intentionally irreversible; legacy data remains archived.")
