"""Publish the verified Cam Coleman annual projection correction.

Revision ID: 0111_sync_cam_coleman_projection
Revises: 0110_player_popularity

The current reviewed projections workbook was checked on 2026-09-05.  This
updates the persisted annual component forecast from that verified row; the
stored total is calculated with the app's PPR scoring contract, rather than
copying the workbook's display-only fantasy total.
"""

from alembic import op


revision = "0111_sync_cam_coleman_projection"
down_revision = "0110_player_popularity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE players
        SET
            sheet_projected_season_points = 281.6,
            sheet_projection_stats = jsonb_build_object(
                'pass_completions', 0.0,
                'pass_attempts', 0.0,
                'pass_yards', 0.0,
                'pass_tds', 0.0,
                'interceptions', 0.0,
                'rush_yards', 26.0,
                'rush_tds', 1.0,
                'receptions', 76.0,
                'rec_yards', 1250.0,
                'rec_tds', 12.0,
                'fg', 0.0,
                'xp', 0.0,
                'fpts', 281.6,
                'source_fantasy_proj', 271.9,
                'scoring_policy_version', 'component_stats_canonical_scoring_v2_beta_flat_kicker',
                'projection_season', 2026
            ),
            sheet_synced_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE
            name = 'Cam Coleman'
            AND school = 'Texas'
            AND UPPER(position) = 'WR'
            AND sheet_source_sheet_id LIKE 'canonical-preseason:2026:%'
        """
    )


def downgrade() -> None:
    # A downgrade must not silently restore an older forecast over the
    # verified source correction.
    pass
