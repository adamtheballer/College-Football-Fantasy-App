from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class LeaguePostseasonSettings(TimestampMixin, Base):
    __tablename__ = "league_postseason_settings"
    __table_args__ = (UniqueConstraint("league_id", "season", name="uq_league_postseason_settings"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    regular_season_start_week: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    regular_season_end_week: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    playoff_start_week: Mapped[int] = mapped_column(Integer, nullable=False, default=11)
    championship_week: Mapped[int] = mapped_column(Integer, nullable=False, default=13)
    playoff_team_count: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
    championship_bracket_size: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
    # Fixed brackets are intentional: a seed remains attached to its route once
    # the postseason begins.  The old column is retained for migration
    # compatibility, but all new code requires it to remain false.
    reseeding_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    third_place_game_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    losers_bracket_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    losers_bracket_name: Mapped[str] = mapped_column(String(80), nullable=False, default="Losers Bracket")
    matchup_finalization_day: Mapped[str] = mapped_column(String(16), nullable=False, default="TUESDAY")
    matchup_finalization_time: Mapped[str] = mapped_column(String(5), nullable=False, default="09:00")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="America/New_York")
    configuration_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PostseasonBracket(TimestampMixin, Base):
    __tablename__ = "postseason_brackets"
    __table_args__ = (
        UniqueConstraint("league_id", "season", name="uq_postseason_bracket_league_season"),
        Index("ix_postseason_brackets_league_season", "league_id", "season"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    bracket_type: Mapped[str] = mapped_column(String(32), nullable=False, default="CHAMPIONSHIP")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="PLANNED")
    total_teams: Mapped[int] = mapped_column(Integer, nullable=False)
    total_rounds: Mapped[int] = mapped_column(Integer, nullable=False)
    regular_season_start_week: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    regular_season_end_week: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    playoff_start_week: Mapped[int] = mapped_column(Integer, nullable=False, default=11)
    max_rounds: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    format_version: Mapped[str] = mapped_column(String(32), nullable=False, default="FIXED_BRACKET_V1")
    tiebreaker_policy: Mapped[str] = mapped_column(String(48), nullable=False, default="HIGHER_SEED_V1")
    lifecycle_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    seeds_locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_kickoff_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    review_metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PostseasonEntry(TimestampMixin, Base):
    __tablename__ = "postseason_entries"
    __table_args__ = (
        UniqueConstraint("bracket_id", "team_id", name="uq_postseason_entry_bracket_team"),
        UniqueConstraint("bracket_id", "bracket_seed", name="uq_postseason_entry_bracket_seed"),
        Index("ix_postseason_entries_bracket", "bracket_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    bracket_id: Mapped[int] = mapped_column(ForeignKey("postseason_brackets.id", ondelete="CASCADE"), nullable=False)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    regular_season_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    bracket_seed: Mapped[int] = mapped_column(Integer, nullable=False)
    qualification_status: Mapped[str] = mapped_column(String(32), nullable=False)
    tiebreaker_explanation: Mapped[str | None] = mapped_column(String(500), nullable=True)
    tiebreak_draw_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    qualified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    final_place: Mapped[int | None] = mapped_column(Integer, nullable=True)
    eliminated_or_escaped_round: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")


class PostseasonRound(TimestampMixin, Base):
    __tablename__ = "postseason_rounds"
    __table_args__ = (UniqueConstraint("bracket_id", "round_number", name="uq_postseason_round_bracket_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    bracket_id: Mapped[int] = mapped_column(ForeignKey("postseason_brackets.id", ondelete="CASCADE"), nullable=False)
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    round_type: Mapped[str] = mapped_column(String(48), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="SCHEDULED")


class PostseasonMatchup(TimestampMixin, Base):
    __tablename__ = "postseason_matchups"
    __table_args__ = (
        UniqueConstraint("round_id", "slot_number", name="uq_postseason_matchup_round_slot"),
        UniqueConstraint("fantasy_matchup_id", name="uq_postseason_matchup_matchup"),
        Index("ix_postseason_matchups_bracket", "bracket_id"),
        Index("ix_postseason_matchups_fantasy_matchup", "fantasy_matchup_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    bracket_id: Mapped[int] = mapped_column(ForeignKey("postseason_brackets.id", ondelete="CASCADE"), nullable=False)
    round_id: Mapped[int] = mapped_column(ForeignKey("postseason_rounds.id", ondelete="CASCADE"), nullable=False)
    fantasy_matchup_id: Mapped[int | None] = mapped_column(ForeignKey("matchups.id", ondelete="SET NULL"), nullable=True)
    slot_number: Mapped[int] = mapped_column(Integer, nullable=False)
    matchup_type: Mapped[str] = mapped_column(String(48), nullable=False, default="CHAMPIONSHIP")
    bracket_path: Mapped[str | None] = mapped_column(String(24), nullable=True)
    team_a_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    team_b_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    team_a_seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    team_b_seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    advancement_rule: Mapped[str] = mapped_column(String(48), nullable=False)
    next_winner_matchup_id: Mapped[int | None] = mapped_column(ForeignKey("postseason_matchups.id", ondelete="SET NULL"), nullable=True)
    next_winner_slot: Mapped[str | None] = mapped_column(String(8), nullable=True)
    next_loser_matchup_id: Mapped[int | None] = mapped_column(ForeignKey("postseason_matchups.id", ondelete="SET NULL"), nullable=True)
    next_loser_slot: Mapped[str | None] = mapped_column(String(8), nullable=True)
    winner_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    loser_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    advancing_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    eliminated_or_safe_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    tiebreaker_used: Mapped[str | None] = mapped_column(String(48), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="SCHEDULED")
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class PostseasonFinalStanding(TimestampMixin, Base):
    __tablename__ = "postseason_final_standings"
    __table_args__ = (
        # Historical rows can legitimately have a nullable bracket ID. Retain
        # the pre-canonical league/season uniqueness guards for those rows;
        # all new service writes additionally satisfy the bracket-scoped
        # canonical constraints below.
        UniqueConstraint("league_id", "season", "team_id", name="uq_postseason_final_standing_team"),
        UniqueConstraint("league_id", "season", "final_place", name="uq_postseason_final_standing_place"),
        UniqueConstraint("bracket_id", "team_id", name="uq_postseason_final_standing_bracket_team"),
        UniqueConstraint("bracket_id", "final_place", name="uq_postseason_final_standing_bracket_place"),
        Index("ix_postseason_final_standings_bracket", "bracket_id", "final_place"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Legacy rows predating canonical playoff materialization can be unlinked;
    # the postseason service requires this for every new result.
    bracket_id: Mapped[int | None] = mapped_column(ForeignKey("postseason_brackets.id", ondelete="SET NULL"), nullable=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    final_place: Mapped[int] = mapped_column(Integer, nullable=False)
    regular_season_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    playoff_seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    postseason_result: Mapped[str] = mapped_column(String(48), nullable=False)
    wins: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    losses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ties: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    points_for: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    finalized_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
