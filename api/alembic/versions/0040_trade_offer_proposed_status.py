"""compatibility placeholder for legacy local trade offer revision

Revision ID: 0040_trade_offer_proposed_status
Revises: 0027_scoring_admin_audits
Create Date: 2026-07-13 00:00:00.000000

This no-op revision preserves a migration identifier that existed in local
development databases but is not present in the current repository history.
It allows those databases to upgrade forward without mutating their
alembic_version table by hand.
"""

from collections.abc import Sequence

revision: str = "0040_trade_offer_proposed_status"
down_revision: str | None = "0027_scoring_admin_audits"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
