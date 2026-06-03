from datetime import datetime
import importlib

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.db.base import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


_MODELS_LOADED = False
_MODEL_MODULES = (
    "collegefootballfantasy_api.app.models.user",
    "collegefootballfantasy_api.app.models.refresh_session",
    "collegefootballfantasy_api.app.models.league",
    "collegefootballfantasy_api.app.models.league_member",
    "collegefootballfantasy_api.app.models.league_settings",
    "collegefootballfantasy_api.app.models.league_invite",
    "collegefootballfantasy_api.app.models.league_week_state",
    "collegefootballfantasy_api.app.models.team",
    "collegefootballfantasy_api.app.models.scheduled_league_job",
    "collegefootballfantasy_api.app.models.admin_action",
    "collegefootballfantasy_api.app.models.idempotency_request",
    "collegefootballfantasy_api.app.models.player",
    "collegefootballfantasy_api.app.models.roster",
    "collegefootballfantasy_api.app.models.transaction",
    "collegefootballfantasy_api.app.models.trade_offer",
    "collegefootballfantasy_api.app.models.trade_offer_item",
    "collegefootballfantasy_api.app.models.waiver_claim",
    "collegefootballfantasy_api.app.models.scoring_run",
    "collegefootballfantasy_api.app.models.matchup",
    "collegefootballfantasy_api.app.models.standing",
    "collegefootballfantasy_api.app.models.injury",
    "collegefootballfantasy_api.app.models.injury_impact",
    "collegefootballfantasy_api.app.models.preseason_prior",
    "collegefootballfantasy_api.app.models.player_stat",
    "collegefootballfantasy_api.app.models.player_game_stat",
    "collegefootballfantasy_api.app.models.game",
    "collegefootballfantasy_api.app.models.team_stats_snapshot",
    "collegefootballfantasy_api.app.models.team_game_stat",
    "collegefootballfantasy_api.app.models.team_week_score",
    "collegefootballfantasy_api.app.models.provider_sync_state",
    "collegefootballfantasy_api.app.models.cfb_standing_snapshot",
    "collegefootballfantasy_api.app.models.draft",
    "collegefootballfantasy_api.app.models.draft_timer_state",
    "collegefootballfantasy_api.app.models.draft_pick",
    "collegefootballfantasy_api.app.models.draft_team_queue_item",
    "collegefootballfantasy_api.app.models.draft_lobby_member",
    "collegefootballfantasy_api.app.models.domain_event",
    "collegefootballfantasy_api.app.models.mock_draft_session",
    "collegefootballfantasy_api.app.models.mock_draft_seat",
    "collegefootballfantasy_api.app.models.mock_draft_pick",
    "collegefootballfantasy_api.app.models.mock_draft_roster",
    "collegefootballfantasy_api.app.models.mock_draft_lobby_member",
    "collegefootballfantasy_api.app.models.mock_draft_timer_state",
    "collegefootballfantasy_api.app.models.mock_draft_queue_item",
    "collegefootballfantasy_api.app.models.mock_draft_event",
    "collegefootballfantasy_api.app.models.player_news_snapshot",
    "collegefootballfantasy_api.app.models.watchlist",
    "collegefootballfantasy_api.app.models.notification",
    "collegefootballfantasy_api.app.models.scheduled_notification",
    "collegefootballfantasy_api.app.models.team_environment",
    "collegefootballfantasy_api.app.models.usage_share",
    "collegefootballfantasy_api.app.models.defense_rating",
    "collegefootballfantasy_api.app.models.weekly_projection",
    "collegefootballfantasy_api.app.models.projection_input_audit",
    "collegefootballfantasy_api.app.models.projection_explanation",
    "collegefootballfantasy_api.app.models.game_odds",
    "collegefootballfantasy_api.app.models.defense_vs_position",
)


def load_model_registry() -> None:
    global _MODELS_LOADED
    if _MODELS_LOADED:
        return
    for module_name in _MODEL_MODULES:
        importlib.import_module(module_name)
    _MODELS_LOADED = True


__all__ = ["Base", "TimestampMixin", "load_model_registry"]
