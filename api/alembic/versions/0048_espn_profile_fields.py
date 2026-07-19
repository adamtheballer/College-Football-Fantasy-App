"""Persist structured ESPN player-profile enrichment fields."""

from alembic import op
import sqlalchemy as sa


revision = "0048_espn_profile_fields"
down_revision = "0047_projection_components"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("players", sa.Column("espn_height_inches", sa.Integer(), nullable=True))
    op.add_column("players", sa.Column("espn_birthplace_city", sa.String(length=120), nullable=True))
    op.add_column("players", sa.Column("espn_birthplace_state", sa.String(length=120), nullable=True))
    op.add_column("players", sa.Column("espn_birthplace_country", sa.String(length=120), nullable=True))
    op.add_column("players", sa.Column("espn_hometown", sa.String(length=300), nullable=True))
    op.add_column("players", sa.Column("espn_date_of_birth", sa.Date(), nullable=True))
    op.add_column("players", sa.Column("espn_source_url", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("players", "espn_source_url")
    op.drop_column("players", "espn_date_of_birth")
    op.drop_column("players", "espn_hometown")
    op.drop_column("players", "espn_birthplace_country")
    op.drop_column("players", "espn_birthplace_state")
    op.drop_column("players", "espn_birthplace_city")
    op.drop_column("players", "espn_height_inches")
