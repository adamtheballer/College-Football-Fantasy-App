"""add provider response cache validators

Revision ID: 0027_response_cache_validators
Revises: 0026_espn_ingestion_cache
Create Date: 2026-07-06 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0027_response_cache_validators"
down_revision: Union[str, None] = "0026_espn_ingestion_cache"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("provider_response_cache", sa.Column("etag", sa.String(length=255), nullable=True))
    op.add_column("provider_response_cache", sa.Column("last_modified", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("provider_response_cache", "last_modified")
    op.drop_column("provider_response_cache", "etag")
