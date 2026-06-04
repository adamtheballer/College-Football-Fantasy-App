from datetime import datetime
import importlib

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from api.app.db.base import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


_MODELS_LOADED = False
_MODEL_MODULES = (
    "api.app.models.user",
    "api.app.models.refresh_session",
    "api.app.models.league",
    "api.app.models.league_member",
    "api.app.models.league_settings",
    "api.app.models.league_invite",
    "api.app.models.league_week_state",
    "api.app.models.team",
    "api.app.models.scheduled_league_job",
    "api.app.models.admin_action",
    "api.app.models.idempotency_request",
    "api.app.models.player",
    "api.app.models.roster",
    "api.app.models.transaction",
    "api.app.models.trade_offer",
    "api.app.models.trade_offer_item",
    "api.app.models.waiver_claim",
    "api.app.models.scoring_run",
    "api.app.models.matchup",
    "api.app.models.standing",
    "api.app.models.injury",
    "api.app.models.injury_impact",
    "api.app.models.preseason_prior",
    "api.app.models.player_stat",
    "api.app.models.lineup",
    "api.app.models.fantasy_player_score",
    "api.app.models.team_weekly_score",
    "api.app.models.player_game_stat",
    "api.app.models.game",
    "api.app.models.team_stats_snapshot",
    "api.app.models.team_game_stat",
    "api.app.models.team_week_score",
    "api.app.models.provider_sync_state",
    "api.app.models.cfb_standing_snapshot",
    "api.app.models.draft",
    "api.app.models.draft_timer_state",
    "api.app.models.draft_pick",
    "api.app.models.draft_team_queue_item",
    "api.app.models.draft_lobby_member",
    "api.app.models.domain_event",
    "api.app.models.mock_draft_session",
    "api.app.models.mock_draft_participant",
    "api.app.models.mock_draft_seat",
    "api.app.models.mock_draft_pick",
    "api.app.models.mock_draft_roster",
    "api.app.models.mock_draft_lobby_member",
    "api.app.models.mock_draft_timer_state",
    "api.app.models.mock_draft_queue_item",
    "api.app.models.mock_draft_event",
    "api.app.models.player_news_snapshot",
    "api.app.models.news_source",
    "api.app.models.news_item",
    "api.app.models.watchlist",
    "api.app.models.notification",
    "api.app.models.scheduled_notification",
    "api.app.models.team_environment",
    "api.app.models.usage_share",
    "api.app.models.defense_rating",
    "api.app.models.weekly_projection",
    "api.app.models.projection_input_audit",
    "api.app.models.projection_explanation",
    "api.app.models.game_odds",
    "api.app.models.defense_vs_position",
)


def load_model_registry() -> None:
    global _MODELS_LOADED
    if _MODELS_LOADED:
        return
    for module_name in _MODEL_MODULES:
        importlib.import_module(module_name)
    _MODELS_LOADED = True


__all__ = ["Base", "TimestampMixin", "load_model_registry"]
