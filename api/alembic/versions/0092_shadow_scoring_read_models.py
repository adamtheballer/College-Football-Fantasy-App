"""Add immutable shadow-only league scoring read models.

Revision ID: 0092_shadow_scoring_read_models
Revises: 0091_live_scoring_hardening
"""

from alembic import op
import sqlalchemy as sa


revision = "0092_shadow_scoring_read_models"
down_revision = "0091_live_scoring_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shadow_scoring_read_models",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("league_id", sa.Integer(), sa.ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("source_sha256", sa.String(length=64), nullable=False),
        sa.Column("calculation_version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "league_id",
            "season",
            "week",
            "source_sha256",
            name="uq_shadow_scoring_read_model_source",
        ),
    )
    op.create_index(
        "ix_shadow_scoring_read_models_league_week",
        "shadow_scoring_read_models",
        ["league_id", "season", "week"],
    )


def downgrade() -> None:
    op.drop_index("ix_shadow_scoring_read_models_league_week", table_name="shadow_scoring_read_models")
    op.drop_table("shadow_scoring_read_models")
