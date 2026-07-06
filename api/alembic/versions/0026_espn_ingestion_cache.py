"""add espn ingestion cache tables

Revision ID: 0026_espn_ingestion_cache
Revises: 0025_scoring_correction_audit
Create Date: 2026-07-06 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0026_espn_ingestion_cache"
down_revision: Union[str, None] = "0025_scoring_correction_audit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "provider_response_cache",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("feed", sa.String(length=120), nullable=False),
        sa.Column("scope_key", sa.String(length=255), nullable=False),
        sa.Column("params_hash", sa.String(length=64), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("params_json", sa.JSON(), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("content_type", sa.String(length=120), nullable=True),
        sa.Column("response_json", sa.JSON(), nullable=True),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "feed",
            "scope_key",
            "params_hash",
            name="uq_provider_response_cache_request",
        ),
    )
    op.create_index(
        "ix_provider_response_cache_provider_feed",
        "provider_response_cache",
        ["provider", "feed"],
    )
    op.create_index("ix_provider_response_cache_expires_at", "provider_response_cache", ["expires_at"])

    op.create_table(
        "provider_ingestion_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("run_date", sa.Date(), nullable=True),
        sa.Column("targets", sa.JSON(), nullable=False),
        sa.Column("dry_run", sa.Boolean(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cache_hits", sa.Integer(), nullable=False),
        sa.Column("cache_misses", sa.Integer(), nullable=False),
        sa.Column("requests_sent", sa.Integer(), nullable=False),
        sa.Column("cache_stale_used", sa.Integer(), nullable=False),
        sa.Column("cache_write_errors", sa.Integer(), nullable=False),
        sa.Column("inserted", sa.Integer(), nullable=False),
        sa.Column("updated", sa.Integer(), nullable=False),
        sa.Column("skipped", sa.Integer(), nullable=False),
        sa.Column("errors", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "college_football_teams",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("external_id", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=True),
        sa.Column("short_name", sa.String(length=120), nullable=True),
        sa.Column("abbreviation", sa.String(length=20), nullable=True),
        sa.Column("location", sa.String(length=120), nullable=True),
        sa.Column("conference", sa.String(length=80), nullable=True),
        sa.Column("color", sa.String(length=20), nullable=True),
        sa.Column("alternate_color", sa.String(length=20), nullable=True),
        sa.Column("logos", sa.JSON(), nullable=False),
        sa.Column("raw_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "external_id", name="uq_cfb_teams_provider_external_id"),
    )
    op.create_index("ix_cfb_teams_name", "college_football_teams", ["name"])

    op.create_table(
        "cfb_ranking_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("poll", sa.String(length=120), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("team_external_id", sa.String(length=80), nullable=False),
        sa.Column("team_name", sa.String(length=200), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("previous_rank", sa.Integer(), nullable=True),
        sa.Column("points", sa.Integer(), nullable=True),
        sa.Column("first_place_votes", sa.Integer(), nullable=True),
        sa.Column("record_summary", sa.String(length=80), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "poll",
            "season",
            "week",
            "team_external_id",
            name="uq_cfb_rankings_provider_poll_week_team",
        ),
    )
    op.create_index("ix_cfb_rankings_season_week", "cfb_ranking_snapshots", ["season", "week"])
    op.create_index("ix_cfb_rankings_poll_rank", "cfb_ranking_snapshots", ["poll", "rank"])


def downgrade() -> None:
    op.drop_index("ix_cfb_rankings_poll_rank", table_name="cfb_ranking_snapshots")
    op.drop_index("ix_cfb_rankings_season_week", table_name="cfb_ranking_snapshots")
    op.drop_table("cfb_ranking_snapshots")
    op.drop_index("ix_cfb_teams_name", table_name="college_football_teams")
    op.drop_table("college_football_teams")
    op.drop_table("provider_ingestion_runs")
    op.drop_index("ix_provider_response_cache_expires_at", table_name="provider_response_cache")
    op.drop_index("ix_provider_response_cache_provider_feed", table_name="provider_response_cache")
    op.drop_table("provider_response_cache")
