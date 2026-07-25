"""Merge the historical waiver-period and projection-stat migration heads."""


# Keep this identifier within the legacy 32-character alembic_version column.
revision = "0059_merge_projection_waiver"
down_revision = ("0058_projection_stat_profiles", "0058_waiver_period_lifecycle")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Merge revision histories after both branch schemas are present."""


def downgrade() -> None:
    """The merge revision has no schema changes to reverse."""
