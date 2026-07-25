"""Harden historical season stats for the reviewed Google Season Stats sheet.

Revision ID: 0068_google_sheet_history
Revises: 0067_split_projection_fg
"""

from alembic import op
import sqlalchemy as sa


revision = "0068_google_sheet_history"
down_revision = "0067_split_projection_fg"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("player_historical_season_stats") as batch_op:
        batch_op.drop_constraint("uq_player_historical_stats_player_provider_season", type_="unique")
        batch_op.add_column(sa.Column("historical_team_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("current_team_at_import_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("source_depth_position", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("canonical_position", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("kick_points", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("source_url", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("source_external_player_id", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("source_type", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("source_modified_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("import_version", sa.String(length=80), nullable=True))
        batch_op.create_foreign_key(
            "fk_historical_season_stats_historical_team",
            "college_teams",
            ["historical_team_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_historical_season_stats_current_team_import",
            "college_teams",
            ["current_team_at_import_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_unique_constraint(
            "uq_player_historical_stats_player_provider_season_team",
            ["player_id", "provider", "season", "season_type", "team_name"],
        )


def downgrade() -> None:
    with op.batch_alter_table("player_historical_season_stats") as batch_op:
        batch_op.drop_constraint("uq_player_historical_stats_player_provider_season_team", type_="unique")
        batch_op.drop_constraint("fk_historical_season_stats_current_team_import", type_="foreignkey")
        batch_op.drop_constraint("fk_historical_season_stats_historical_team", type_="foreignkey")
        batch_op.drop_column("import_version")
        batch_op.drop_column("source_modified_at")
        batch_op.drop_column("source_type")
        batch_op.drop_column("source_external_player_id")
        batch_op.drop_column("source_url")
        batch_op.drop_column("kick_points")
        batch_op.drop_column("canonical_position")
        batch_op.drop_column("source_depth_position")
        batch_op.drop_column("current_team_at_import_id")
        batch_op.drop_column("historical_team_id")
        batch_op.create_unique_constraint(
            "uq_player_historical_stats_player_provider_season",
            ["player_id", "provider", "season", "season_type"],
        )
