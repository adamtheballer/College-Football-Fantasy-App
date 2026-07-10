from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.db.base import Base
from collegefootballfantasy_api.app.models import (
    audit_event,
    cfb_standing_snapshot,
    cfb_ranking_snapshot,
    college_football_team,
    defense_rating,
    defense_vs_position,
    draft,
    draft_event,
    draft_pick,
    draft_queue_entry,
    game,
    game_odds,
    injury,
    injury_impact,
    league,
    league_invite,
    league_member,
    league_message,
    league_settings,
    league_settings_version,
    lineup_change_event,
    lineup_week_snapshot,
    matchup,
    matchup_score_version,
    mock_draft,
    mock_draft_pick,
    mock_draft_queue_entry,
    notification,
    player,
    player_game_stat,
    player_stat,
    player_week_score,
    preseason_prior,
    provider_player_identity_audit,
    provider_ingestion_run,
    provider_response_cache,
    provider_sync_job,
    provider_sync_state,
    provider_unmatched_player_row,
    projection_explanation,
    projection_input_audit,
    refresh_session,
    roster,
    scheduled_notification,
    scoring_job_lock,
    scoring_correction_audit,
    scoring_run,
    standing,
    team,
    team_environment,
    team_provider_id,
    team_stats_snapshot,
    team_game_stat,
    team_week_score,
    trade_offer,
    trade_offer_item,
    trade_review,
    user,
    usage_share,
    waiver_claim,
    waiver_priority,
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
