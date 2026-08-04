"""Add privacy-preserving moderation audit events.

Revision ID: 0086_content_moderation_events
Revises: 0085_persist_draft_order
Create Date: 2026-08-04
"""

from alembic import op
import sqlalchemy as sa


revision = "0086_content_moderation_events"
down_revision = "0085_persist_draft_order"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "moderation_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("league_id", sa.Integer(), nullable=True),
        sa.Column("field_name", sa.String(length=80), nullable=False),
        sa.Column("reason_code", sa.String(length=80), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_moderation_events_actor_created", "moderation_events", ["actor_user_id", "created_at"])
    op.create_index("ix_moderation_events_league_created", "moderation_events", ["league_id", "created_at"])
    op.create_index("ix_moderation_events_reason_created", "moderation_events", ["reason_code", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_moderation_events_reason_created", table_name="moderation_events")
    op.drop_index("ix_moderation_events_league_created", table_name="moderation_events")
    op.drop_index("ix_moderation_events_actor_created", table_name="moderation_events")
    op.drop_table("moderation_events")
