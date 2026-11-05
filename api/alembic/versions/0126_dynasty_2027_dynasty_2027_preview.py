"""dynasty_2027_preview

Revision ID: 0126_dynasty_2027
Revises: 0125_challenge_experiences
Create Date: 2026-10-27 00:00:39.311369
"""

from alembic import op
import sqlalchemy as sa

revision = "0126_dynasty_2027"
down_revision = "0125_challenge_experiences"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dynasty_leagues",
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("commissioner_user_id", sa.Integer(), nullable=False),
        sa.Column("max_teams", sa.Integer(), nullable=False),
        sa.Column("invite_code", sa.String(length=30), nullable=False),
        sa.Column("startup_season", sa.Integer(), nullable=False),
        sa.Column("current_season", sa.Integer(), nullable=False),
        sa.Column("roster_limit", sa.Integer(), nullable=False),
        sa.Column("startup_rounds", sa.Integer(), nullable=False),
        sa.Column("freshman_rounds", sa.Integer(), nullable=False),
        sa.Column("future_pick_years", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "max_teams BETWEEN 2 AND 24 AND roster_limit BETWEEN 2 AND 100 AND startup_rounds > 0 AND startup_rounds <= roster_limit AND freshman_rounds BETWEEN 1 AND 20 AND freshman_rounds <= roster_limit AND future_pick_years BETWEEN 1 AND 3",
            name="ck_dynasty_configuration",
        ),
        sa.CheckConstraint(
            "startup_season >= 2027 AND current_season >= startup_season",
            name="ck_dynasty_future_season",
        ),
        sa.ForeignKeyConstraint(
            ["commissioner_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("league_id"),
        sa.UniqueConstraint("invite_code"),
    )
    op.create_table(
        "dynasty_player_seasons",
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("entry_season", sa.Integer(), nullable=False),
        sa.Column("school", sa.String(length=200), nullable=False),
        sa.Column("academic_class", sa.String(length=12), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("eligible", sa.Boolean(), nullable=False),
        sa.Column("reviewed", sa.Boolean(), nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=False),
        sa.Column("base_value", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "base_value IS NULL OR base_value BETWEEN 0 AND 100",
            name="ck_dynasty_base_value",
        ),
        sa.CheckConstraint(
            "season >= 2027 AND entry_season >= 2000 AND entry_season <= season",
            name="ck_dynasty_catalog_season",
        ),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("player_id", "season"),
    )
    op.create_table(
        "dynasty_franchises",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["league_id"], ["dynasty_leagues.league_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("league_id", "id", name="uq_dynasty_franchise_scope"),
        sa.UniqueConstraint("league_id", "name", name="uq_dynasty_franchise_name"),
        sa.UniqueConstraint(
            "league_id", "owner_user_id", name="uq_dynasty_franchise_owner"
        ),
    )
    op.create_index(
        op.f("ix_dynasty_franchises_league_id"),
        "dynasty_franchises",
        ["league_id"],
        unique=False,
    )
    op.create_table(
        "dynasty_seasons",
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("draft_kind", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("order_json", sa.JSON(), nullable=False),
        sa.Column("pool_json", sa.JSON(), nullable=False),
        sa.Column("pick_cursor", sa.Integer(), nullable=False),
        sa.Column("results_json", sa.JSON(), nullable=False),
        sa.Column("roster_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("departures_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "draft_kind IN ('startup','freshman') AND status IN ('scheduled','drafting','complete','closed')",
            name="ck_dynasty_season_state",
        ),
        sa.CheckConstraint(
            "season >= 2027 AND pick_cursor >= 0", name="ck_dynasty_season_cursor"
        ),
        sa.ForeignKeyConstraint(
            ["league_id"], ["dynasty_leagues.league_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("league_id", "season"),
    )
    op.create_table(
        "dynasty_pick_assets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("original_team_id", sa.Integer(), nullable=False),
        sa.Column("owner_team_id", sa.Integer(), nullable=False),
        sa.Column("overall_pick", sa.Integer(), nullable=True),
        sa.Column("player_id", sa.Integer(), nullable=True),
        sa.Column("picked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "season >= 2027 AND round_number > 0 AND (overall_pick IS NULL OR overall_pick > 0)",
            name="ck_dynasty_pick_number",
        ),
        sa.ForeignKeyConstraint(
            ["league_id", "original_team_id"],
            ["dynasty_franchises.league_id", "dynasty_franchises.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["league_id", "owner_team_id"],
            ["dynasty_franchises.league_id", "dynasty_franchises.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "league_id", "season", "overall_pick", name="uq_dynasty_overall_pick"
        ),
        sa.UniqueConstraint(
            "league_id", "season", "player_id", name="uq_dynasty_drafted_player"
        ),
        sa.UniqueConstraint(
            "league_id",
            "season",
            "round_number",
            "original_team_id",
            name="uq_dynasty_origin_pick",
        ),
    )
    op.create_index(
        op.f("ix_dynasty_pick_assets_league_id"),
        "dynasty_pick_assets",
        ["league_id"],
        unique=False,
    )
    op.create_table(
        "dynasty_rosters",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["league_id", "team_id"],
            ["dynasty_franchises.league_id", "dynasty_franchises.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "league_id", "player_id", name="uq_dynasty_rostered_player"
        ),
    )
    op.create_index(
        op.f("ix_dynasty_rosters_league_id"),
        "dynasty_rosters",
        ["league_id"],
        unique=False,
    )
    op.create_table(
        "dynasty_trades",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("from_team_id", sa.Integer(), nullable=False),
        sa.Column("to_team_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("assets_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "from_team_id != to_team_id AND status IN ('pending','accepted','cancelled','rejected')",
            name="ck_dynasty_trade_state",
        ),
        sa.ForeignKeyConstraint(
            ["league_id", "from_team_id"],
            ["dynasty_franchises.league_id", "dynasty_franchises.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["league_id", "to_team_id"],
            ["dynasty_franchises.league_id", "dynasty_franchises.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_dynasty_trades_league_id"),
        "dynasty_trades",
        ["league_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_dynasty_trades_league_id"), table_name="dynasty_trades")
    op.drop_table("dynasty_trades")
    op.drop_index(op.f("ix_dynasty_rosters_league_id"), table_name="dynasty_rosters")
    op.drop_table("dynasty_rosters")
    op.drop_index(
        op.f("ix_dynasty_pick_assets_league_id"), table_name="dynasty_pick_assets"
    )
    op.drop_table("dynasty_pick_assets")
    op.drop_table("dynasty_seasons")
    op.drop_index(
        op.f("ix_dynasty_franchises_league_id"), table_name="dynasty_franchises"
    )
    op.drop_table("dynasty_franchises")
    op.drop_table("dynasty_player_seasons")
    op.drop_table("dynasty_leagues")
