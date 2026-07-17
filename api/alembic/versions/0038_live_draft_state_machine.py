"""persist authoritative live draft state

Revision ID: 0038_live_draft_state
Revises: 0037_trade_counter_link
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0038_live_draft_state"
down_revision: str | Sequence[str] | None = "0037_trade_counter_link"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    draft_columns = {column["name"] for column in inspector.get_columns("drafts")}
    draft_additions = (
        ("pre_draft_starts_at", sa.DateTime(timezone=True), True, None),
        ("draft_starts_at", sa.DateTime(timezone=True), True, None),
        ("current_pick_number", sa.Integer(), False, "0"),
        ("current_pick_started_at", sa.DateTime(timezone=True), True, None),
        ("current_pick_deadline", sa.DateTime(timezone=True), True, None),
        ("transition_ends_at", sa.DateTime(timezone=True), True, None),
        ("draft_version", sa.Integer(), False, "0"),
        ("completed_at", sa.DateTime(timezone=True), True, None),
    )
    for name, column_type, nullable, default in draft_additions:
        if name not in draft_columns:
            op.add_column("drafts", sa.Column(name, column_type, nullable=nullable, server_default=default))
            if default is not None:
                op.alter_column("drafts", name, existing_type=column_type, server_default=None)

    pick_columns = {column["name"] for column in inspector.get_columns("draft_picks")}
    if "auto_pick" not in pick_columns:
        op.add_column(
            "draft_picks",
            sa.Column("auto_pick", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        op.alter_column("draft_picks", "auto_pick", existing_type=sa.Boolean(), server_default=None)

    draft_indexes = {index["name"] for index in inspector.get_indexes("drafts")}
    if "ix_drafts_live_state" not in draft_indexes:
        op.create_index("ix_drafts_live_state", "drafts", ["status", "draft_starts_at"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    draft_indexes = {index["name"] for index in inspector.get_indexes("drafts")}
    if "ix_drafts_live_state" in draft_indexes:
        op.drop_index("ix_drafts_live_state", table_name="drafts")
    pick_columns = {column["name"] for column in inspector.get_columns("draft_picks")}
    if "auto_pick" in pick_columns:
        op.drop_column("draft_picks", "auto_pick")
    draft_columns = {column["name"] for column in inspector.get_columns("drafts")}
    for name in (
        "completed_at",
        "draft_version",
        "transition_ends_at",
        "current_pick_deadline",
        "current_pick_started_at",
        "current_pick_number",
        "draft_starts_at",
        "pre_draft_starts_at",
    ):
        if name in draft_columns:
            op.drop_column("drafts", name)
