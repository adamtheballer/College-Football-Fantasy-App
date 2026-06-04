"""add news wire tables

Revision ID: 0037_news_wire
Revises: 0036_mock_draft_mode
Create Date: 2026-06-04 00:30:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0037_news_wire"
down_revision: str | None = "0036_mock_draft_mode"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "news_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("source_type", sa.String(length=30), nullable=False),
        sa.Column("url", sa.String(length=600), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("poll_interval_minutes", sa.Integer(), nullable=False),
        sa.Column("last_polled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_news_sources_active"), "news_sources", ["active"], unique=False)
    op.create_index(op.f("ix_news_sources_name"), "news_sources", ["name"], unique=True)
    op.create_index(op.f("ix_news_sources_priority"), "news_sources", ["priority"], unique=False)
    op.create_index(op.f("ix_news_sources_source_type"), "news_sources", ["source_type"], unique=False)
    op.create_table(
        "news_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.String(length=300), nullable=True),
        sa.Column("source_name", sa.String(length=120), nullable=False),
        sa.Column("source_url", sa.String(length=900), nullable=False),
        sa.Column("source_type", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=True),
        sa.Column("player_name_raw", sa.String(length=200), nullable=True),
        sa.Column("team_name_raw", sa.String(length=200), nullable=True),
        sa.Column("canonical_team", sa.String(length=200), nullable=True),
        sa.Column("position", sa.String(length=10), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("fantasy_relevance_score", sa.Float(), nullable=False),
        sa.Column("fantasy_impact", sa.Text(), nullable=True),
        sa.Column("tags_json", sa.JSON(), nullable=False),
        sa.Column("raw_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_news_items_canonical_team", "news_items", ["canonical_team"], unique=False)
    op.create_index("ix_news_items_category", "news_items", ["category"], unique=False)
    op.create_index("ix_news_items_content_hash", "news_items", ["content_hash"], unique=True)
    op.create_index("ix_news_items_fantasy_relevance_score", "news_items", ["fantasy_relevance_score"], unique=False)
    op.create_index("ix_news_items_player_id", "news_items", ["player_id"], unique=False)
    op.create_index("ix_news_items_published_at", "news_items", ["published_at"], unique=False)
    op.create_index("ix_news_items_source_name", "news_items", ["source_name"], unique=False)
    op.create_index("ix_news_items_source_url", "news_items", ["source_url"], unique=False)
    op.create_index("ix_news_items_status", "news_items", ["status"], unique=False)
    op.execute(
        "INSERT INTO news_sources "
        "(name, source_type, url, active, priority, poll_interval_minutes) "
        "VALUES ('College Football News', 'html_index', 'https://collegefootballnews.com/', true, 80, 60) "
        "ON CONFLICT (name) DO NOTHING"
    )


def downgrade() -> None:
    op.drop_index("ix_news_items_status", table_name="news_items")
    op.drop_index("ix_news_items_source_url", table_name="news_items")
    op.drop_index("ix_news_items_source_name", table_name="news_items")
    op.drop_index("ix_news_items_published_at", table_name="news_items")
    op.drop_index("ix_news_items_player_id", table_name="news_items")
    op.drop_index("ix_news_items_fantasy_relevance_score", table_name="news_items")
    op.drop_index("ix_news_items_content_hash", table_name="news_items")
    op.drop_index("ix_news_items_category", table_name="news_items")
    op.drop_index("ix_news_items_canonical_team", table_name="news_items")
    op.drop_table("news_items")
    op.drop_index(op.f("ix_news_sources_source_type"), table_name="news_sources")
    op.drop_index(op.f("ix_news_sources_priority"), table_name="news_sources")
    op.drop_index(op.f("ix_news_sources_name"), table_name="news_sources")
    op.drop_index(op.f("ix_news_sources_active"), table_name="news_sources")
    op.drop_table("news_sources")
