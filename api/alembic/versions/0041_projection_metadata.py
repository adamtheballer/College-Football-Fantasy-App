"""projection metadata

Revision ID: 0041_projection_metadata
Revises: 0040_league_chat
Create Date: 2026-07-06
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0041_projection_metadata"
down_revision = "0040_league_chat"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("weekly_projections") as batch_op:
        batch_op.add_column(sa.Column("projection_version", sa.Integer(), nullable=False, server_default="1"))
        batch_op.add_column(sa.Column("model_version", sa.String(length=50), nullable=False, server_default="projection-v1"))
        batch_op.add_column(sa.Column("input_snapshot_hash", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("source_freshness", sa.String(length=30), nullable=False, server_default="unknown"))
        batch_op.add_column(sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0.5"))

    with op.batch_alter_table("projection_explanations") as batch_op:
        batch_op.add_column(sa.Column("input_snapshot_hash", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("explanation", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0.5"))
        batch_op.add_column(sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table("projection_inputs_audit") as batch_op:
        batch_op.add_column(sa.Column("input_snapshot_hash", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("source_freshness", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("projection_inputs_audit") as batch_op:
        batch_op.drop_column("generated_at")
        batch_op.drop_column("source_freshness")
        batch_op.drop_column("input_snapshot_hash")

    with op.batch_alter_table("projection_explanations") as batch_op:
        batch_op.drop_column("generated_at")
        batch_op.drop_column("confidence_score")
        batch_op.drop_column("explanation")
        batch_op.drop_column("input_snapshot_hash")

    with op.batch_alter_table("weekly_projections") as batch_op:
        batch_op.drop_column("confidence_score")
        batch_op.drop_column("source_freshness")
        batch_op.drop_column("generated_at")
        batch_op.drop_column("input_snapshot_hash")
        batch_op.drop_column("model_version")
        batch_op.drop_column("projection_version")
