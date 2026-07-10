"""add player provider ids

Revision ID: 0044_player_provider_ids
Revises: 0043_watchlist_metadata_alerts
Create Date: 2026-07-09 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "0044_player_provider_ids"
down_revision: str | None = "0043_watchlist_metadata_alerts"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "player_provider_ids",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("provider_player_id", sa.String(length=120), nullable=False),
        sa.Column("provider_team_id", sa.String(length=120), nullable=True),
        sa.Column("match_confidence", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["verified_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_player_id", name="uq_player_provider_ids_provider_player"),
        sa.UniqueConstraint("player_id", "provider", name="uq_player_provider_ids_player_provider"),
    )
    op.create_index("ix_player_provider_ids_player_id", "player_provider_ids", ["player_id"], unique=False)
    op.create_index(
        "ix_player_provider_ids_provider_team",
        "player_provider_ids",
        ["provider", "provider_team_id"],
        unique=False,
    )

    bind = op.get_bind()
    players = bind.execute(sa.text("SELECT id, external_id FROM players WHERE external_id IS NOT NULL")).fetchall()
    for player_id, external_id in players:
        raw_external_id = str(external_id or "").strip()
        if not raw_external_id:
            continue
        provider = "sportsdata"
        provider_player_id = raw_external_id
        if raw_external_id.lower().startswith("espn:"):
            provider = "espn"
            provider_player_id = raw_external_id.split(":", 1)[1].strip()
        elif raw_external_id.lower().startswith("sportsdata:"):
            provider = "sportsdata"
            provider_player_id = raw_external_id.split(":", 1)[1].strip()
        if not provider_player_id:
            continue
        bind.execute(
            sa.text(
                """
                INSERT INTO player_provider_ids (
                    player_id, provider, provider_player_id, match_confidence, created_at, updated_at
                )
                SELECT :player_id, :provider, :provider_player_id, 100, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                WHERE NOT EXISTS (
                    SELECT 1 FROM player_provider_ids
                    WHERE provider = :provider AND provider_player_id = :provider_player_id
                )
                """
            ),
            {"player_id": player_id, "provider": provider, "provider_player_id": provider_player_id},
        )


def downgrade() -> None:
    op.drop_index("ix_player_provider_ids_provider_team", table_name="player_provider_ids")
    op.drop_index("ix_player_provider_ids_player_id", table_name="player_provider_ids")
    op.drop_table("player_provider_ids")
