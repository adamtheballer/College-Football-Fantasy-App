"""league settings versions and invite controls

Revision ID: 0033_league_settings_versions_invite_controls
Revises: 0032_matchup_score_versions
Create Date: 2026-07-06
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0033_league_settings_versions_invite_controls"
down_revision = "0032_matchup_score_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.alter_column(
            "alembic_version",
            "version_num",
            existing_type=sa.String(length=32),
            type_=sa.String(length=255),
        )

    op.create_table(
        "league_settings_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("settings_json", sa.JSON(), nullable=False),
        sa.Column("effective_season", sa.Integer(), nullable=False),
        sa.Column("effective_week", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("league_id", "version", name="uq_league_settings_versions_league_version"),
    )
    op.create_index("ix_league_settings_versions_league_id", "league_settings_versions", ["league_id"])

    with op.batch_alter_table("league_invites") as batch_op:
        batch_op.add_column(sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("max_uses", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("uses_count", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("email_domain", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("league_invites") as batch_op:
        batch_op.drop_column("revoked_at")
        batch_op.drop_column("email_domain")
        batch_op.drop_column("uses_count")
        batch_op.drop_column("max_uses")
        batch_op.drop_column("expires_at")

    op.drop_index("ix_league_settings_versions_league_id", table_name="league_settings_versions")
    op.drop_table("league_settings_versions")
