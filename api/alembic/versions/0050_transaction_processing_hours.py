"""Restrict waiver and trade processing to daytime hours."""

from alembic import op
import sqlalchemy as sa


revision = "0050_tx_processing_window"
down_revision = "0049_player_bio_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
        UPDATE league_settings
        SET waiver_process_hour = 8,
            next_waiver_run_at = NULL
        WHERE waiver_process_hour < 8 OR waiver_process_hour > 22
        """
        )
    )

    if bind.dialect.name != "postgresql":
        return

    for table_name, status_value in (("waiver_claims", "pending"), ("trade_offers", "accepted_pending")):
        bind.execute(
            sa.text(
                f"""
            UPDATE {table_name} AS transaction_row
            SET process_after = (
                date_trunc(
                    'day',
                    transaction_row.process_after AT TIME ZONE COALESCE(draft.timezone, 'America/New_York')
                ) + INTERVAL '8 hours'
            ) AT TIME ZONE COALESCE(draft.timezone, 'America/New_York')
            FROM leagues AS league
            LEFT JOIN drafts AS draft ON draft.league_id = league.id
            WHERE transaction_row.league_id = league.id
              AND transaction_row.status = '{status_value}'
              AND transaction_row.process_after IS NOT NULL
              AND (
                EXTRACT(HOUR FROM transaction_row.process_after AT TIME ZONE COALESCE(draft.timezone, 'America/New_York')) < 8
                OR EXTRACT(HOUR FROM transaction_row.process_after AT TIME ZONE COALESCE(draft.timezone, 'America/New_York')) > 22
              )
            """
            )
        )


def downgrade() -> None:
    # Existing schedules must not be moved back to overnight processing.
    pass
