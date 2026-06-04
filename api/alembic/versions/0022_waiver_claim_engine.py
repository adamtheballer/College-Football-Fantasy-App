"""add waiver claims and team waiver state fields

Revision ID: 0022_waiver_claim_engine
Revises: 0021_week_state_trade_lifecycle
Create Date: 2026-05-26 12:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0022_waiver_claim_engine"
down_revision: str | None = "0021_week_state_trade_lifecycle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("teams", sa.Column("waiver_priority", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("teams", sa.Column("faab_balance", sa.Integer(), nullable=False, server_default="100"))

    op.create_table(
        "waiver_claims",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("add_player_id", sa.Integer(), nullable=False),
        sa.Column("drop_player_id", sa.Integer(), nullable=True),
        sa.Column("bid_amount", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("priority_snapshot", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("process_batch_key", sa.String(length=80), nullable=True),
        sa.Column("processed_reason", sa.String(length=255), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["add_player_id"], ["players.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["drop_player_id"], ["players.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_waiver_claims_league_id_status",
        "waiver_claims",
        ["league_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_waiver_claims_league_id_created_at",
        "waiver_claims",
        ["league_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_waiver_claims_team_id_status",
        "waiver_claims",
        ["team_id", "status"],
        unique=False,
    )
    op.create_index("ix_waiver_claims_add_player_id", "waiver_claims", ["add_player_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_waiver_claims_add_player_id", table_name="waiver_claims")
    op.drop_index("ix_waiver_claims_team_id_status", table_name="waiver_claims")
    op.drop_index("ix_waiver_claims_league_id_created_at", table_name="waiver_claims")
    op.drop_index("ix_waiver_claims_league_id_status", table_name="waiver_claims")
    op.drop_table("waiver_claims")

    op.drop_column("teams", "faab_balance")
    op.drop_column("teams", "waiver_priority")
