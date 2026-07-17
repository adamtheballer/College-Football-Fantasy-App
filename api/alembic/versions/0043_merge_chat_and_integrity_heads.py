"""Merge the chat and fantasy-integrity migration branches.

Revision ID: 0043_merge_chat_integrity
Revises: 0042_espn_profile, 0039_chat_query_indexes
Create Date: 2026-07-17 00:00:00.000000
"""

from collections.abc import Sequence


revision: str = "0043_merge_chat_integrity"
down_revision: str | Sequence[str] | None = ("0042_espn_profile", "0039_chat_query_indexes")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
