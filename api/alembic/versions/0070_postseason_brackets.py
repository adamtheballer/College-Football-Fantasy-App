"""Persist canonical league postseason configuration and bracket history.

Revision ID: 0070_postseason_brackets
Revises: 0069_trade_asset_snapshots
"""

from alembic import op
import sqlalchemy as sa


revision = "0070_postseason_brackets"
down_revision = "0069_trade_asset_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "league_postseason_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("league_id", sa.Integer(), sa.ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("regular_season_start_week", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("regular_season_end_week", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("playoff_start_week", sa.Integer(), nullable=False, server_default="11"),
        sa.Column("championship_week", sa.Integer(), nullable=False, server_default="13"),
        sa.Column("playoff_team_count", sa.Integer(), nullable=False, server_default="6"),
        sa.Column("championship_bracket_size", sa.Integer(), nullable=False, server_default="6"),
        sa.Column("reseeding_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("third_place_game_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("losers_bracket_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("losers_bracket_name", sa.String(length=80), nullable=False, server_default="Losers Bracket"),
        sa.Column("matchup_finalization_day", sa.String(length=16), nullable=False, server_default="TUESDAY"),
        sa.Column("matchup_finalization_time", sa.String(length=5), nullable=False, server_default="09:00"),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="America/New_York"),
        sa.Column("configuration_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("league_id", "season", name="uq_league_postseason_settings"),
    )
    op.create_table(
        "postseason_brackets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("league_id", sa.Integer(), sa.ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("bracket_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="SCHEDULED"),
        sa.Column("total_teams", sa.Integer(), nullable=False),
        sa.Column("total_rounds", sa.Integer(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("league_id", "season", "bracket_type", name="uq_postseason_bracket_league_season_type"),
    )
    op.create_index("ix_postseason_brackets_league_season", "postseason_brackets", ["league_id", "season"])
    op.create_table(
        "postseason_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bracket_id", sa.Integer(), sa.ForeignKey("postseason_brackets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("regular_season_rank", sa.Integer(), nullable=False),
        sa.Column("bracket_seed", sa.Integer(), nullable=False),
        sa.Column("qualification_status", sa.String(length=32), nullable=False),
        sa.Column("tiebreaker_explanation", sa.String(length=500), nullable=True),
        sa.Column("qualified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("final_place", sa.Integer(), nullable=True),
        sa.Column("eliminated_or_escaped_round", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("bracket_id", "team_id", name="uq_postseason_entry_bracket_team"),
        sa.UniqueConstraint("bracket_id", "bracket_seed", name="uq_postseason_entry_bracket_seed"),
    )
    op.create_index("ix_postseason_entries_bracket", "postseason_entries", ["bracket_id"])
    op.create_table(
        "postseason_rounds",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bracket_id", sa.Integer(), sa.ForeignKey("postseason_brackets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("round_type", sa.String(length=48), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="SCHEDULED"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("bracket_id", "round_number", name="uq_postseason_round_bracket_number"),
    )
    op.create_table(
        "postseason_matchups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bracket_id", sa.Integer(), sa.ForeignKey("postseason_brackets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("round_id", sa.Integer(), sa.ForeignKey("postseason_rounds.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fantasy_matchup_id", sa.Integer(), sa.ForeignKey("matchups.id", ondelete="SET NULL"), nullable=True),
        sa.Column("slot_number", sa.Integer(), nullable=False),
        sa.Column("team_a_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="SET NULL"), nullable=True),
        sa.Column("team_b_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="SET NULL"), nullable=True),
        sa.Column("team_a_seed", sa.Integer(), nullable=True),
        sa.Column("team_b_seed", sa.Integer(), nullable=True),
        sa.Column("advancement_rule", sa.String(length=48), nullable=False),
        sa.Column("advancing_team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="SET NULL"), nullable=True),
        sa.Column("eliminated_or_safe_team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="SET NULL"), nullable=True),
        sa.Column("tiebreaker_used", sa.String(length=48), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="SCHEDULED"),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("round_id", "slot_number", name="uq_postseason_matchup_round_slot"),
        sa.UniqueConstraint("fantasy_matchup_id", name="uq_postseason_matchup_matchup"),
    )
    op.create_index("ix_postseason_matchups_bracket", "postseason_matchups", ["bracket_id"])
    op.create_table(
        "postseason_final_standings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("league_id", sa.Integer(), sa.ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("final_place", sa.Integer(), nullable=False),
        sa.Column("regular_season_rank", sa.Integer(), nullable=False),
        sa.Column("playoff_seed", sa.Integer(), nullable=True),
        sa.Column("postseason_result", sa.String(length=48), nullable=False),
        sa.Column("wins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("losses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ties", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("points_for", sa.Float(), nullable=False, server_default="0"),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("league_id", "season", "team_id", name="uq_postseason_final_standing_team"),
        sa.UniqueConstraint("league_id", "season", "final_place", name="uq_postseason_final_standing_place"),
    )
    op.execute(
        """
        WITH normalized AS (
            SELECT
                l.id AS league_id,
                l.season_year AS season,
                CASE
                    WHEN l.max_teams = 2 THEN 2
                    WHEN l.max_teams = 4 AND COALESCE(s.playoff_teams, 2) IN (2, 4) THEN s.playoff_teams
                    WHEN l.max_teams = 4 THEN 2
                    WHEN l.max_teams = 6 THEN 4
                    WHEN l.max_teams = 8 AND COALESCE(s.playoff_teams, 6) IN (4, 6) THEN s.playoff_teams
                    WHEN l.max_teams = 8 THEN 6
                    WHEN l.max_teams IN (10, 12) AND COALESCE(s.playoff_teams, 6) IN (4, 6, 8) THEN s.playoff_teams
                    WHEN l.max_teams = 10 THEN 6
                    ELSE 8
                END AS playoff_team_count
            FROM leagues l
            LEFT JOIN league_settings s ON s.league_id = l.id
        )
        INSERT INTO league_postseason_settings (
            league_id, season, regular_season_start_week, regular_season_end_week,
            playoff_start_week, championship_week, playoff_team_count,
            championship_bracket_size, reseeding_enabled, third_place_game_enabled,
            losers_bracket_enabled, losers_bracket_name, matchup_finalization_day,
            matchup_finalization_time, timezone, configuration_version
        )
        SELECT
            league_id, season, 1, 10, 11, 13, playoff_team_count,
            playoff_team_count, true, true, true, 'Losers Bracket', 'TUESDAY',
            '09:00', 'America/New_York', 1
        FROM normalized
        """
    )


def downgrade() -> None:
    op.drop_table("postseason_final_standings")
    op.drop_index("ix_postseason_matchups_bracket", table_name="postseason_matchups")
    op.drop_table("postseason_matchups")
    op.drop_table("postseason_rounds")
    op.drop_index("ix_postseason_entries_bracket", table_name="postseason_entries")
    op.drop_table("postseason_entries")
    op.drop_index("ix_postseason_brackets_league_season", table_name="postseason_brackets")
    op.drop_table("postseason_brackets")
    op.drop_table("league_postseason_settings")
