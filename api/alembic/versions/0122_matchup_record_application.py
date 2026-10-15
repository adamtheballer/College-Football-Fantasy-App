"""Persist exact applied-result receipts without inferring legacy application."""
from alembic import op
import sqlalchemy as sa

revision = '0122_matchup_record_application'
down_revision = '0121_player_chart_forecast'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('matchups', sa.Column('record_application_fingerprint', sa.String(64), nullable=True))


def downgrade():
    op.drop_column('matchups', 'record_application_fingerprint')
