"""league invariant constraints

Revision ID: 0013_league_invariants
Revises: 0012_notif_user_ids
Create Date: 2026-03-21 19:45:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0013_league_invariants"
down_revision = "0012_notif_user_ids"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("teams") as batch_op:
        batch_op.create_unique_constraint("uq_team_league_owner", ["league_id", "owner_user_id"])

    with op.batch_alter_table("roster_entries") as batch_op:
        batch_op.add_column(sa.Column("league_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_roster_entries_league_id_leagues",
            "leagues",
            ["league_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_index("ix_roster_entries_league_id", ["league_id"], unique=False)
        batch_op.create_index("ix_roster_entries_league_player", ["league_id", "player_id"], unique=False)

    op.execute(
        sa.text(
            """
            UPDATE roster_entries
            SET league_id = teams.league_id
            FROM teams
            WHERE roster_entries.team_id = teams.id
              AND roster_entries.league_id IS NULL
            """
        )
    )

    with op.batch_alter_table("roster_entries") as batch_op:
        batch_op.alter_column("league_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_unique_constraint("uq_roster_league_player", ["league_id", "player_id"])


def downgrade() -> None:
    with op.batch_alter_table("roster_entries") as batch_op:
        batch_op.drop_constraint("uq_roster_league_player", type_="unique")
        batch_op.drop_index("ix_roster_entries_league_player")
        batch_op.drop_index("ix_roster_entries_league_id")
        batch_op.drop_constraint("fk_roster_entries_league_id_leagues", type_="foreignkey")
        batch_op.drop_column("league_id")

    with op.batch_alter_table("teams") as batch_op:
        batch_op.drop_constraint("uq_team_league_owner", type_="unique")
