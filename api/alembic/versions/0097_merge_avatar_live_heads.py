"""Merge manager-avatar and live-projection migration heads.

Revision ID: 0097_merge_avatar_live_heads
Revises: 0091_manager_profile_avatar_url, 0096_live_player_projections
Create Date: 2026-08-19
"""


revision = "0097_merge_avatar_live_heads"
down_revision = (
    "0091_manager_profile_avatar_url",
    "0096_live_player_projections",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Join independent migration branches without changing schema."""
    pass


def downgrade() -> None:
    """Restore the two prior migration heads without changing schema."""
    pass
