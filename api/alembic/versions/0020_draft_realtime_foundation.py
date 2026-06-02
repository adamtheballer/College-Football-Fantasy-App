"""add domain events, draft timer state, and idempotency key for draft picks

Revision ID: 0020_draft_realtime_foundation
Revises: 0019_sheet_proj_stats
Create Date: 2026-05-26 00:00:01.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0020_draft_realtime_foundation"
down_revision: str | None = "0019_sheet_proj_stats"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "domain_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("entity_type", sa.String(length=120), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_domain_events_event_type", "domain_events", ["event_type"], unique=False)
    op.create_index("ix_domain_events_league_id_id", "domain_events", ["league_id", "id"], unique=False)
    op.create_index(
        "ix_domain_events_league_id_occurred_at",
        "domain_events",
        ["league_id", "occurred_at"],
        unique=False,
    )

    op.create_table(
        "draft_timer_states",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("draft_id", sa.Integer(), nullable=False),
        sa.Column("timer_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paused_total_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_tick_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("state_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["draft_id"], ["drafts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("draft_id", name="uq_draft_timer_states_draft_id"),
    )
    op.create_index("ix_draft_timer_states_draft_id", "draft_timer_states", ["draft_id"], unique=False)

    op.add_column("draft_picks", sa.Column("idempotency_key", sa.String(length=128), nullable=True))
    op.create_index(
        "ix_draft_picks_draft_id_idempotency_key",
        "draft_picks",
        ["draft_id", "idempotency_key"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_draft_picks_draft_id_idempotency_key",
        "draft_picks",
        ["draft_id", "idempotency_key"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_draft_picks_draft_id_idempotency_key", "draft_picks", type_="unique")
    op.drop_index("ix_draft_picks_draft_id_idempotency_key", table_name="draft_picks")
    op.drop_column("draft_picks", "idempotency_key")

    op.drop_index("ix_draft_timer_states_draft_id", table_name="draft_timer_states")
    op.drop_table("draft_timer_states")

    op.drop_index("ix_domain_events_league_id_occurred_at", table_name="domain_events")
    op.drop_index("ix_domain_events_league_id_id", table_name="domain_events")
    op.drop_index("ix_domain_events_event_type", table_name="domain_events")
    op.drop_table("domain_events")
