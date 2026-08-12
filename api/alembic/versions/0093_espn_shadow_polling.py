"""add ESPN shadow polling state

Revision ID: 0093_espn_shadow_polling
Revises: 0092_shadow_scoring_read_models
"""

from alembic import op
import sqlalchemy as sa


revision = "0093_espn_shadow_polling"
down_revision = "0092_shadow_scoring_read_models"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_game_poll_states",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_game_id", sa.String(length=128), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("lifecycle_state", sa.String(length=30), nullable=False),
        sa.Column("final_fetch_stage", sa.String(length=30), nullable=False),
        sa.Column("next_poll_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_scoreboard_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_polled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rate_limited_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("last_error_category", sa.String(length=80), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("operator_status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_game_id", name="uq_provider_game_poll_state"),
    )
    op.create_index("ix_provider_game_poll_states_due", "provider_game_poll_states", ["provider", "next_poll_at"])
    op.create_index("ix_provider_game_poll_states_game", "provider_game_poll_states", ["game_id"])
    op.create_table(
        "provider_polling_health",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("circuit_state", sa.String(length=30), nullable=False),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False),
        sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_http_status", sa.Integer(), nullable=True),
        sa.Column("last_error_category", sa.String(length=80), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider"),
    )


def downgrade() -> None:
    op.drop_table("provider_polling_health")
    op.drop_index("ix_provider_game_poll_states_game", table_name="provider_game_poll_states")
    op.drop_index("ix_provider_game_poll_states_due", table_name="provider_game_poll_states")
    op.drop_table("provider_game_poll_states")
