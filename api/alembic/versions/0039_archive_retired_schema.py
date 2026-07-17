"""Archive tables no longer owned by the application schema.

Revision ID: 0039_archive_retired_schema
Revises: 0038_live_draft_state
Create Date: 2026-07-15 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0039_archive_retired_schema"
down_revision: str | None = "0038_live_draft_state"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


RETIRED_TABLES = (
    "admin_actions",
    "audit_events",
    "billing_customers",
    "billing_events",
    "billing_subscriptions",
    "domain_events",
    "draft_lobby_members",
    "draft_team_queue_items",
    "draft_timer_states",
    "entitlement_audit",
    "entitlement_state",
    "fantasy_player_scores",
    "idempotency_requests",
    "league_settings_versions",
    "league_week_states",
    "lineup_entries",
    "lineups",
    "mock_draft_events",
    "mock_draft_lobby_members",
    "mock_draft_participants",
    "mock_draft_queue_items",
    "mock_draft_roster_entries",
    "mock_draft_seats",
    "mock_draft_sessions",
    "mock_draft_timer_states",
    "news_items",
    "news_sources",
    "player_news_snapshots",
    "scheduled_league_jobs",
    "team_weekly_scores",
)


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    existing_tables = _table_names()
    for table_name in RETIRED_TABLES:
        archive_table_name = f"legacy_archive_{table_name}"
        if table_name not in existing_tables or archive_table_name in existing_tables:
            continue
        op.rename_table(table_name, archive_table_name)


def downgrade() -> None:
    existing_tables = _table_names()
    for table_name in reversed(RETIRED_TABLES):
        archive_table_name = f"legacy_archive_{table_name}"
        if archive_table_name not in existing_tables or table_name in existing_tables:
            continue
        op.rename_table(archive_table_name, table_name)
