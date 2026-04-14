from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.db.base import Base
from collegefootballfantasy_api.app.models import (
    cfb_standing_snapshot,
    defense_rating,
    defense_vs_position,
    draft,
    game,
    game_odds,
    injury,
    injury_impact,
    league,
    league_invite,
    league_member,
    league_settings,
    matchup,
    notification,
    player,
    player_game_stat,
    player_stat,
    preseason_prior,
    provider_sync_state,
    projection_explanation,
    projection_input_audit,
    refresh_session,
    roster,
    scheduled_notification,
    standing,
    team,
    team_environment,
    team_stats_snapshot,
    team_game_stat,
    team_week_score,
    user,
    usage_share,
    weekly_projection,
)

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
