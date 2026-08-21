"""Harden the dormant postseason schema for canonical fixed brackets.

Revision ID: 0102_postseason_playoffs
Revises: 0101_injury_notification_scope
"""

from alembic import op
import sqlalchemy as sa


revision = "0102_postseason_playoffs"
down_revision = "0101_injury_notification_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("league_postseason_settings", "reseeding_enabled", existing_type=sa.Boolean(), server_default=sa.false())
    # Calendar provenance is snapshotted with each league plan. It records the
    # sealed schedule artifact that certified the date reservation, rather than
    # trusting mutable imported rows or a live provider response later.
    for column in (
        sa.Column("calendar_policy_version", sa.String(length=48), nullable=False, server_default="P4_FULL_COVERAGE_V2"),
        sa.Column("calendar_source_identity", sa.String(length=256), nullable=False, server_default="UNSET"),
        sa.Column("calendar_source_revision", sa.String(length=128), nullable=False, server_default="UNSET"),
        sa.Column("calendar_source_sha256", sa.String(length=64), nullable=False, server_default="UNSET"),
        sa.Column("calendar_source_format_version", sa.String(length=48), nullable=False, server_default="SEALED_CFB_SCHEDULE_V1"),
    ):
        op.add_column("league_postseason_settings", column)

    op.drop_constraint("uq_postseason_bracket_league_season_type", "postseason_brackets", type_="unique")
    op.create_unique_constraint("uq_postseason_bracket_league_season", "postseason_brackets", ["league_id", "season"])
    for name, column in (
        ("regular_season_start_week", sa.Column("regular_season_start_week", sa.Integer(), nullable=False, server_default="1")),
        ("regular_season_end_week", sa.Column("regular_season_end_week", sa.Integer(), nullable=False, server_default="10")),
        ("playoff_start_week", sa.Column("playoff_start_week", sa.Integer(), nullable=False, server_default="11")),
        ("championship_week", sa.Column("championship_week", sa.Integer(), nullable=False, server_default="13")),
        ("max_rounds", sa.Column("max_rounds", sa.Integer(), nullable=False, server_default="1")),
        ("calendar_policy_version", sa.Column("calendar_policy_version", sa.String(length=48), nullable=False, server_default="P4_FULL_COVERAGE_V2")),
        ("calendar_source_identity", sa.Column("calendar_source_identity", sa.String(length=256), nullable=False, server_default="UNSET")),
        ("calendar_source_revision", sa.Column("calendar_source_revision", sa.String(length=128), nullable=False, server_default="UNSET")),
        ("calendar_source_sha256", sa.Column("calendar_source_sha256", sa.String(length=64), nullable=False, server_default="UNSET")),
        ("calendar_source_format_version", sa.Column("calendar_source_format_version", sa.String(length=48), nullable=False, server_default="SEALED_CFB_SCHEDULE_V1")),
        ("format_version", sa.Column("format_version", sa.String(length=32), nullable=False, server_default="FIXED_BRACKET_V1")),
        ("tiebreaker_policy", sa.Column("tiebreaker_policy", sa.String(length=48), nullable=False, server_default="HIGHER_SEED_V1")),
        ("lifecycle_version", sa.Column("lifecycle_version", sa.Integer(), nullable=False, server_default="1")),
    ):
        op.add_column("postseason_brackets", column)
    op.add_column("postseason_brackets", sa.Column("seeds_locked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("postseason_brackets", sa.Column("first_kickoff_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("postseason_brackets", sa.Column("review_reason", sa.String(length=1000), nullable=True))
    op.add_column("postseason_brackets", sa.Column("review_metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    op.execute("UPDATE postseason_brackets SET status = 'PLANNED' WHERE status = 'SCHEDULED'")

    op.add_column("postseason_entries", sa.Column("tiebreak_draw_key", sa.String(length=128), nullable=True))

    op.add_column("postseason_matchups", sa.Column("matchup_type", sa.String(length=48), nullable=False, server_default="CHAMPIONSHIP"))
    op.add_column("postseason_matchups", sa.Column("bracket_path", sa.String(length=24), nullable=True))
    op.add_column("postseason_matchups", sa.Column("next_winner_matchup_id", sa.Integer(), nullable=True))
    op.add_column("postseason_matchups", sa.Column("next_winner_slot", sa.String(length=8), nullable=True))
    op.add_column("postseason_matchups", sa.Column("next_loser_matchup_id", sa.Integer(), nullable=True))
    op.add_column("postseason_matchups", sa.Column("next_loser_slot", sa.String(length=8), nullable=True))
    op.add_column("postseason_matchups", sa.Column("winner_team_id", sa.Integer(), nullable=True))
    op.add_column("postseason_matchups", sa.Column("loser_team_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_postseason_matchups_next_winner", "postseason_matchups", "postseason_matchups", ["next_winner_matchup_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_postseason_matchups_next_loser", "postseason_matchups", "postseason_matchups", ["next_loser_matchup_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_postseason_matchups_winner_team", "postseason_matchups", "teams", ["winner_team_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_postseason_matchups_loser_team", "postseason_matchups", "teams", ["loser_team_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_postseason_matchups_fantasy_matchup", "postseason_matchups", ["fantasy_matchup_id"])

    # Preserve legacy final standings even if their pre-feature data has no
    # matching bracket. New service writes always include a bracket ID.
    op.add_column("postseason_final_standings", sa.Column("bracket_id", sa.Integer(), nullable=True))
    op.execute(
        """
        UPDATE postseason_final_standings AS standings
        SET bracket_id = bracket.id
        FROM postseason_brackets AS bracket
        WHERE bracket.league_id = standings.league_id AND bracket.season = standings.season
        """
    )
    op.create_foreign_key("fk_postseason_final_standings_bracket", "postseason_final_standings", "postseason_brackets", ["bracket_id"], ["id"], ondelete="SET NULL")
    op.create_unique_constraint("uq_postseason_final_standing_bracket_team", "postseason_final_standings", ["bracket_id", "team_id"])
    op.create_unique_constraint("uq_postseason_final_standing_bracket_place", "postseason_final_standings", ["bracket_id", "final_place"])
    op.create_index("ix_postseason_final_standings_bracket", "postseason_final_standings", ["bracket_id", "final_place"])


def downgrade() -> None:
    op.drop_index("ix_postseason_final_standings_bracket", table_name="postseason_final_standings")
    op.drop_constraint("uq_postseason_final_standing_bracket_place", "postseason_final_standings", type_="unique")
    op.drop_constraint("uq_postseason_final_standing_bracket_team", "postseason_final_standings", type_="unique")
    op.drop_constraint("fk_postseason_final_standings_bracket", "postseason_final_standings", type_="foreignkey")
    op.drop_column("postseason_final_standings", "bracket_id")
    op.drop_index("ix_postseason_matchups_fantasy_matchup", table_name="postseason_matchups")
    for constraint in ("fk_postseason_matchups_loser_team", "fk_postseason_matchups_winner_team", "fk_postseason_matchups_next_loser", "fk_postseason_matchups_next_winner"):
        op.drop_constraint(constraint, "postseason_matchups", type_="foreignkey")
    for name in ("loser_team_id", "winner_team_id", "next_loser_slot", "next_loser_matchup_id", "next_winner_slot", "next_winner_matchup_id", "bracket_path", "matchup_type"):
        op.drop_column("postseason_matchups", name)
    op.drop_column("postseason_entries", "tiebreak_draw_key")
    for name in ("review_metadata_json", "review_reason", "first_kickoff_at", "seeds_locked_at", "lifecycle_version", "tiebreaker_policy", "format_version", "calendar_source_format_version", "calendar_source_sha256", "calendar_source_revision", "calendar_source_identity", "calendar_policy_version", "max_rounds", "championship_week", "playoff_start_week", "regular_season_end_week", "regular_season_start_week"):
        op.drop_column("postseason_brackets", name)
    for name in ("calendar_source_format_version", "calendar_source_sha256", "calendar_source_revision", "calendar_source_identity", "calendar_policy_version"):
        op.drop_column("league_postseason_settings", name)
    op.drop_constraint("uq_postseason_bracket_league_season", "postseason_brackets", type_="unique")
    op.create_unique_constraint("uq_postseason_bracket_league_season_type", "postseason_brackets", ["league_id", "season", "bracket_type"])
    op.alter_column("league_postseason_settings", "reseeding_enabled", existing_type=sa.Boolean(), server_default=sa.true())
