"""Publish the verified Trent Mosley catalog addition and Cam Coleman correction.

Revision ID: 0112_add_trent_mosley_and_correct_cam_coleman
Revises: 0111_sync_cam_coleman_projection

The live reviewed annual-projections workbook was checked on 2026-09-05. Its
Trent Mosley row was absent from the older sealed release snapshot, so the
canonical-pool predicate correctly excluded him from drafts. This migration
makes that verified USC WR row available on both existing and fresh releases.

Cam Coleman's manual source correction is a receiving touchdown, not a rushing
touchdown. Keep the component profile explicit so the annual total is always
derived by the same PPR scoring contract used everywhere else.
"""

from alembic import op


# ``alembic_version.version_num`` is VARCHAR(32) in the deployed schema.
revision = "0112_trent_mosley_cam_correction"
down_revision = "0111_sync_cam_coleman_projection"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Update first so an existing provider-created row becomes the one canonical
    # player record rather than creating an ambiguous duplicate identity.
    op.execute(
        """
        UPDATE players
        SET
            player_class = 'Freshman',
            sheet_bio_class = 'FR',
            sheet_bio_source_sheet_id = 'canonical-preseason:2026:2026-09-05-live-projection-correction:Big10',
            sheet_bio_synced_at = CURRENT_TIMESTAMP,
            sheet_projected_season_points = 245.5,
            sheet_projection_stats = jsonb_build_object(
                'pass_completions', 0.0,
                'pass_attempts', 0.0,
                'pass_yards', 0.0,
                'pass_tds', 0.0,
                'interceptions', 0.0,
                'rush_yards', 55.0,
                'rush_tds', 1.0,
                'receptions', 65.0,
                'rec_yards', 1150.0,
                'rec_tds', 9.0,
                'fg', 0.0,
                'xp', 0.0,
                'fpts', 245.5,
                'source_fantasy_proj', 245.5,
                'scoring_policy_version', 'component_stats_canonical_scoring_v2_beta_flat_kicker',
                'projection_season', 2026
            ),
            sheet_source_sheet_id = 'canonical-preseason:2026:2026-09-05-live-projection-correction:Big10',
            sheet_synced_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE
            name = 'Trent Mosley'
            AND school = 'USC'
            AND UPPER(position) = 'WR'
        """
    )
    op.execute(
        """
        INSERT INTO players (
            name,
            position,
            school,
            player_class,
            sheet_bio_class,
            sheet_bio_source_sheet_id,
            sheet_bio_synced_at,
            sheet_projected_season_points,
            sheet_projection_stats,
            sheet_source_sheet_id,
            sheet_synced_at,
            created_at,
            updated_at
        )
        SELECT
            'Trent Mosley',
            'WR',
            'USC',
            'Freshman',
            'FR',
            'canonical-preseason:2026:2026-09-05-live-projection-correction:Big10',
            CURRENT_TIMESTAMP,
            245.5,
            jsonb_build_object(
                'pass_completions', 0.0,
                'pass_attempts', 0.0,
                'pass_yards', 0.0,
                'pass_tds', 0.0,
                'interceptions', 0.0,
                'rush_yards', 55.0,
                'rush_tds', 1.0,
                'receptions', 65.0,
                'rec_yards', 1150.0,
                'rec_tds', 9.0,
                'fg', 0.0,
                'xp', 0.0,
                'fpts', 245.5,
                'source_fantasy_proj', 245.5,
                'scoring_policy_version', 'component_stats_canonical_scoring_v2_beta_flat_kicker',
                'projection_season', 2026
            ),
            'canonical-preseason:2026:2026-09-05-live-projection-correction:Big10',
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        WHERE NOT EXISTS (
            SELECT 1
            FROM players
            WHERE
                name = 'Trent Mosley'
                AND school = 'USC'
                AND UPPER(position) = 'WR'
        )
        """
    )
    op.execute(
        """
        UPDATE players
        SET
            sheet_projected_season_points = 284.6,
            sheet_projection_stats = jsonb_build_object(
                'pass_completions', 0.0,
                'pass_attempts', 0.0,
                'pass_yards', 0.0,
                'pass_tds', 0.0,
                'interceptions', 0.0,
                'rush_yards', 26.0,
                'rush_tds', 0.0,
                'receptions', 79.0,
                'rec_yards', 1250.0,
                'rec_tds', 13.0,
                'fg', 0.0,
                'xp', 0.0,
                'fpts', 284.6,
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
    # Do not restore the obsolete component projection or remove a player who
    # may already have roster/draft history.
    pass
