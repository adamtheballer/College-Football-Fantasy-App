"""roster transactions and watchlists

Revision ID: 0011_roster_watchlists
Revises: 0010_draft_picks
Create Date: 2026-03-21 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0011_roster_watchlists"
down_revision = "0010_draft_picks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("transaction_type", sa.String(length=50), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=True),
        sa.Column("related_player_id", sa.Integer(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["related_player_id"], ["players.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_transactions_league_id", "transactions", ["league_id"], unique=False)
    op.create_index("ix_transactions_team_id", "transactions", ["team_id"], unique=False)
    op.create_index("ix_transactions_created_at", "transactions", ["created_at"], unique=False)

    op.create_table(
        "watchlists",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_watchlists_user_id", "watchlists", ["user_id"], unique=False)
    op.create_index("ix_watchlists_league_id", "watchlists", ["league_id"], unique=False)

    op.create_table(
        "watchlist_players",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("watchlist_id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["watchlist_id"], ["watchlists.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("watchlist_id", "player_id", name="uq_watchlist_players_watchlist_player"),
    )
    op.create_index("ix_watchlist_players_watchlist_id", "watchlist_players", ["watchlist_id"], unique=False)
    op.create_index("ix_watchlist_players_player_id", "watchlist_players", ["player_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_watchlist_players_player_id", table_name="watchlist_players")
    op.drop_index("ix_watchlist_players_watchlist_id", table_name="watchlist_players")
    op.drop_table("watchlist_players")

    op.drop_index("ix_watchlists_league_id", table_name="watchlists")
    op.drop_index("ix_watchlists_user_id", table_name="watchlists")
    op.drop_table("watchlists")

    op.drop_index("ix_transactions_created_at", table_name="transactions")
    op.drop_index("ix_transactions_team_id", table_name="transactions")
    op.drop_index("ix_transactions_league_id", table_name="transactions")
    op.drop_table("transactions")
