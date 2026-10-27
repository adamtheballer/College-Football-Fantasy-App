"""Future-season preview facts; existing redraft records are not converted."""

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class DynastyLeague(TimestampMixin, Base):
    __tablename__ = "dynasty_leagues"
    __table_args__ = (
        CheckConstraint(
            "startup_season >= 2027 AND current_season >= startup_season",
            name="ck_dynasty_future_season",
        ),
        CheckConstraint(
            "max_teams BETWEEN 2 AND 24 AND roster_limit BETWEEN 2 AND 100 AND startup_rounds > 0 AND startup_rounds <= roster_limit AND freshman_rounds BETWEEN 1 AND 20 AND freshman_rounds <= roster_limit AND future_pick_years BETWEEN 1 AND 3",
            name="ck_dynasty_configuration",
        ),
    )
    league_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    commissioner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    max_teams: Mapped[int] = mapped_column(Integer)
    invite_code: Mapped[str] = mapped_column(String(30), unique=True)
    startup_season: Mapped[int] = mapped_column(Integer)
    current_season: Mapped[int] = mapped_column(Integer)
    roster_limit: Mapped[int] = mapped_column(Integer)
    startup_rounds: Mapped[int] = mapped_column(Integer)
    freshman_rounds: Mapped[int] = mapped_column(Integer)
    future_pick_years: Mapped[int] = mapped_column(Integer)


class DynastyFranchise(TimestampMixin, Base):
    __tablename__ = "dynasty_franchises"
    __table_args__ = (
        UniqueConstraint("league_id", "id", name="uq_dynasty_franchise_scope"),
        UniqueConstraint(
            "league_id", "owner_user_id", name="uq_dynasty_franchise_owner"
        ),
        UniqueConstraint("league_id", "name", name="uq_dynasty_franchise_name"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(
        ForeignKey("dynasty_leagues.league_id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(80))
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )


class DynastyRoster(TimestampMixin, Base):
    __tablename__ = "dynasty_rosters"
    __table_args__ = (
        UniqueConstraint("league_id", "player_id", name="uq_dynasty_rostered_player"),
        ForeignKeyConstraint(
            ["league_id", "team_id"],
            ["dynasty_franchises.league_id", "dynasty_franchises.id"],
            ondelete="CASCADE",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(Integer, index=True)
    team_id: Mapped[int] = mapped_column(Integer)
    player_id: Mapped[int] = mapped_column(
        ForeignKey("players.id", ondelete="RESTRICT")
    )


class DynastySeason(TimestampMixin, Base):
    __tablename__ = "dynasty_seasons"
    __table_args__ = (
        CheckConstraint(
            "season >= 2027 AND pick_cursor >= 0", name="ck_dynasty_season_cursor"
        ),
        CheckConstraint(
            "draft_kind IN ('startup','freshman') AND status IN ('scheduled','drafting','complete','closed')",
            name="ck_dynasty_season_state",
        ),
    )
    league_id: Mapped[int] = mapped_column(
        ForeignKey("dynasty_leagues.league_id", ondelete="CASCADE"), primary_key=True
    )
    season: Mapped[int] = mapped_column(Integer, primary_key=True)
    draft_kind: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="scheduled")
    order_json: Mapped[list] = mapped_column(JSON, default=list)
    pool_json: Mapped[list] = mapped_column(JSON, default=list)
    pick_cursor: Mapped[int] = mapped_column(Integer, default=0)
    results_json: Mapped[list] = mapped_column(JSON, default=list)
    roster_snapshot_json: Mapped[list] = mapped_column(JSON, default=list)
    departures_json: Mapped[list] = mapped_column(JSON, default=list)


class DynastyPlayerSeason(TimestampMixin, Base):
    __tablename__ = "dynasty_player_seasons"
    __table_args__ = (
        CheckConstraint(
            "season >= 2027 AND entry_season >= 2000 AND entry_season <= season",
            name="ck_dynasty_catalog_season",
        ),
        CheckConstraint(
            "base_value IS NULL OR base_value BETWEEN 0 AND 100",
            name="ck_dynasty_base_value",
        ),
    )
    player_id: Mapped[int] = mapped_column(
        ForeignKey("players.id", ondelete="CASCADE"), primary_key=True
    )
    season: Mapped[int] = mapped_column(Integer, primary_key=True)
    entry_season: Mapped[int] = mapped_column(Integer)
    school: Mapped[str] = mapped_column(String(200))
    academic_class: Mapped[str] = mapped_column(String(12))
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    eligible: Mapped[bool] = mapped_column(Boolean)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    source_url: Mapped[str] = mapped_column(String(1000))
    base_value: Mapped[float | None] = mapped_column(Float, nullable=True)


class DynastyPickAsset(TimestampMixin, Base):
    __tablename__ = "dynasty_pick_assets"
    __table_args__ = (
        UniqueConstraint(
            "league_id",
            "season",
            "round_number",
            "original_team_id",
            name="uq_dynasty_origin_pick",
        ),
        UniqueConstraint(
            "league_id", "season", "overall_pick", name="uq_dynasty_overall_pick"
        ),
        UniqueConstraint(
            "league_id", "season", "player_id", name="uq_dynasty_drafted_player"
        ),
        ForeignKeyConstraint(
            ["league_id", "original_team_id"],
            ["dynasty_franchises.league_id", "dynasty_franchises.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["league_id", "owner_team_id"],
            ["dynasty_franchises.league_id", "dynasty_franchises.id"],
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "season >= 2027 AND round_number > 0 AND (overall_pick IS NULL OR overall_pick > 0)",
            name="ck_dynasty_pick_number",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(Integer, index=True)
    season: Mapped[int] = mapped_column(Integer)
    round_number: Mapped[int] = mapped_column(Integer)
    original_team_id: Mapped[int] = mapped_column(Integer)
    owner_team_id: Mapped[int] = mapped_column(Integer)
    overall_pick: Mapped[int | None] = mapped_column(Integer, nullable=True)
    player_id: Mapped[int | None] = mapped_column(
        ForeignKey("players.id", ondelete="RESTRICT"), nullable=True
    )
    picked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class DynastyTrade(TimestampMixin, Base):
    __tablename__ = "dynasty_trades"
    __table_args__ = (
        ForeignKeyConstraint(
            ["league_id", "from_team_id"],
            ["dynasty_franchises.league_id", "dynasty_franchises.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["league_id", "to_team_id"],
            ["dynasty_franchises.league_id", "dynasty_franchises.id"],
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "from_team_id != to_team_id AND status IN ('pending','accepted','cancelled','rejected')",
            name="ck_dynasty_trade_state",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(Integer, index=True)
    from_team_id: Mapped[int] = mapped_column(Integer)
    to_team_id: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    assets_json: Mapped[list] = mapped_column(JSON)
