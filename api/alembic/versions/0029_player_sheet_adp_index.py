"""add player sheet adp index

Revision ID: 0029_player_sheet_adp_index
Revises: 0028_historical_player_stats
Create Date: 2026-07-14 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0029_player_sheet_adp_index"
down_revision: str | None = "0028_historical_player_stats"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_players_sheet_adp", "players", ["sheet_adp"])


def downgrade() -> None:
    op.drop_index("ix_players_sheet_adp", table_name="players")
