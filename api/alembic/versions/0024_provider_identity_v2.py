"""Add provider identity v2 tables.

Revision ID: 0024_provider_identity_v2
Revises: 0023_trade_offer_lifecycle
Create Date: 2026-07-10 00:00:00.000000
"""

from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op


revision: str = "0024_provider_identity_v2"
down_revision: str | None = "0023_trade_offer_lifecycle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _backfill_player_provider_ids() -> None:
    bind = op.get_bind()
    players = sa.table(
        "players",
        sa.column("id", sa.Integer),
        sa.column("external_id", sa.String),
    )
    mappings = sa.table(
        "player_provider_ids",
        sa.column("player_id", sa.Integer),
        sa.column("provider", sa.String),
        sa.column("provider_player_id", sa.String),
        sa.column("match_confidence", sa.Float),
        sa.column("verification_status", sa.String),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    now = datetime.now(timezone.utc)
    rows = bind.execute(sa.select(players.c.id, players.c.external_id).where(players.c.external_id.is_not(None))).all()
    seen_provider_ids: set[tuple[str, str]] = set()
    seen_player_providers: set[tuple[int, str]] = set()
    for player_id, external_id in rows:
        raw_external_id = str(external_id or "").strip()
        if not raw_external_id:
            continue
        provider = "sportsdata"
        provider_player_id = raw_external_id
        if raw_external_id.lower().startswith("espn:"):
            provider = "espn"
            provider_player_id = raw_external_id.split(":", 1)[1]
        elif ":" in raw_external_id:
            provider, provider_player_id = raw_external_id.split(":", 1)
            provider = provider.strip().lower() or "unknown"
            provider_player_id = provider_player_id.strip()
        if not provider_player_id:
            continue
        provider_key = (provider, provider_player_id)
        player_provider_key = (player_id, provider)
        if provider_key in seen_provider_ids or player_provider_key in seen_player_providers:
            continue
        seen_provider_ids.add(provider_key)
        seen_player_providers.add(player_provider_key)
        bind.execute(
            mappings.insert().values(
                player_id=player_id,
                provider=provider,
                provider_player_id=provider_player_id,
                match_confidence=1.0,
                verification_status="legacy_backfill",
                created_at=now,
                updated_at=now,
            )
        )


def upgrade() -> None:
    op.add_column("users", sa.Column("is_admin", sa.Boolean(), server_default=sa.text("false"), nullable=False))

    op.create_table(
        "college_teams",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("conference", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_college_teams_name"),
    )
    op.create_index("ix_college_teams_conference", "college_teams", ["conference"])

    op.create_table(
        "player_provider_ids",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_player_id", sa.String(length=128), nullable=False),
        sa.Column("provider_team_id", sa.String(length=128), nullable=True),
        sa.Column("match_confidence", sa.Float(), nullable=True),
        sa.Column("verification_status", sa.String(length=30), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["verified_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_player_id", name="uq_player_provider_ids_provider_player"),
        sa.UniqueConstraint("player_id", "provider", name="uq_player_provider_ids_player_provider"),
    )
    op.create_index("ix_player_provider_ids_player_id", "player_provider_ids", ["player_id"])
    op.create_index("ix_player_provider_ids_provider", "player_provider_ids", ["provider"])
    op.create_index(
        "ix_player_provider_ids_verification_status",
        "player_provider_ids",
        ["verification_status"],
    )

    op.create_table(
        "team_provider_ids",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_team_id", sa.String(length=128), nullable=False),
        sa.Column("provider_team_name", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["team_id"], ["college_teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_team_id", name="uq_team_provider_ids_provider_team"),
        sa.UniqueConstraint("team_id", "provider", name="uq_team_provider_ids_team_provider"),
    )
    op.create_index("ix_team_provider_ids_team_id", "team_provider_ids", ["team_id"])
    op.create_index("ix_team_provider_ids_provider", "team_provider_ids", ["provider"])

    op.create_table(
        "unmatched_provider_rows",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("feed", sa.String(length=100), nullable=False),
        sa.Column("season", sa.Integer(), nullable=True),
        sa.Column("week", sa.Integer(), nullable=True),
        sa.Column("provider_player_id", sa.String(length=128), nullable=True),
        sa.Column("provider_team_id", sa.String(length=128), nullable=True),
        sa.Column("player_name", sa.String(length=200), nullable=True),
        sa.Column("team_name", sa.String(length=200), nullable=True),
        sa.Column("dedupe_hash", sa.String(length=64), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("occurrence_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by_user_id", sa.Integer(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("mapped_player_id", sa.Integer(), nullable=True),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["mapped_player_id"], ["players.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["resolved_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "feed", "dedupe_hash", name="uq_unmatched_provider_rows_provider_feed_hash"),
    )
    op.create_index("ix_unmatched_provider_rows_status", "unmatched_provider_rows", ["status"])
    op.create_index(
        "ix_unmatched_provider_rows_provider_feed",
        "unmatched_provider_rows",
        ["provider", "feed"],
    )
    op.create_index(
        "ix_unmatched_provider_rows_provider_player_id",
        "unmatched_provider_rows",
        ["provider_player_id"],
    )
    op.create_index(
        "ix_unmatched_provider_rows_provider_team_id",
        "unmatched_provider_rows",
        ["provider_team_id"],
    )

    op.create_table(
        "provider_identity_audits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("provider_player_id", sa.String(length=128), nullable=True),
        sa.Column("provider_team_id", sa.String(length=128), nullable=True),
        sa.Column("unmatched_row_id", sa.Integer(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("before_state", sa.JSON(), nullable=True),
        sa.Column("after_state", sa.JSON(), nullable=True),
        sa.Column("reason", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["unmatched_row_id"], ["unmatched_provider_rows.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_provider_identity_audits_entity",
        "provider_identity_audits",
        ["entity_type", "entity_id"],
    )
    op.create_index("ix_provider_identity_audits_provider", "provider_identity_audits", ["provider"])
    op.create_index("ix_provider_identity_audits_actor_user_id", "provider_identity_audits", ["actor_user_id"])

    _backfill_player_provider_ids()


def downgrade() -> None:
    op.drop_index("ix_provider_identity_audits_actor_user_id", table_name="provider_identity_audits")
    op.drop_index("ix_provider_identity_audits_provider", table_name="provider_identity_audits")
    op.drop_index("ix_provider_identity_audits_entity", table_name="provider_identity_audits")
    op.drop_table("provider_identity_audits")

    op.drop_index("ix_unmatched_provider_rows_provider_team_id", table_name="unmatched_provider_rows")
    op.drop_index("ix_unmatched_provider_rows_provider_player_id", table_name="unmatched_provider_rows")
    op.drop_index("ix_unmatched_provider_rows_provider_feed", table_name="unmatched_provider_rows")
    op.drop_index("ix_unmatched_provider_rows_status", table_name="unmatched_provider_rows")
    op.drop_table("unmatched_provider_rows")

    op.drop_index("ix_team_provider_ids_provider", table_name="team_provider_ids")
    op.drop_index("ix_team_provider_ids_team_id", table_name="team_provider_ids")
    op.drop_table("team_provider_ids")

    op.drop_index("ix_player_provider_ids_verification_status", table_name="player_provider_ids")
    op.drop_index("ix_player_provider_ids_provider", table_name="player_provider_ids")
    op.drop_index("ix_player_provider_ids_player_id", table_name="player_provider_ids")
    op.drop_table("player_provider_ids")

    op.drop_index("ix_college_teams_conference", table_name="college_teams")
    op.drop_table("college_teams")

    op.drop_column("users", "is_admin")
