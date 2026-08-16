"""Add immutable audit records for approved legacy kicker scoring corrections.

Revision ID: 0093_legacy_kicker_scoring_audit
Revises: 0092_espn_shadow_game_polls
Create Date: 2026-08-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0093_legacy_kicker_scoring_audit"
down_revision: str | None = "0092_espn_shadow_game_polls"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "league_scoring_migrations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("league_settings_id", sa.Integer(), nullable=False),
        sa.Column("migration_key", sa.String(length=120), nullable=False),
        sa.Column("reason", sa.String(length=120), nullable=False),
        sa.Column("before_scoring_json", sa.JSON(), nullable=False),
        sa.Column("before_scoring_snapshot_json", sa.JSON(), nullable=True),
        sa.Column("after_scoring_json", sa.JSON(), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["league_settings_id"], ["league_settings.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("league_id", "migration_key", name="uq_league_scoring_migrations_league_key"),
    )
    op.create_index("ix_league_scoring_migrations_league_id", "league_scoring_migrations", ["league_id"])
    op.create_index("ix_league_scoring_migrations_migration_key", "league_scoring_migrations", ["migration_key"])


def downgrade() -> None:
    op.drop_index("ix_league_scoring_migrations_migration_key", table_name="league_scoring_migrations")
    op.drop_index("ix_league_scoring_migrations_league_id", table_name="league_scoring_migrations")
    op.drop_table("league_scoring_migrations")
