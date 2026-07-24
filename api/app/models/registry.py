"""Explicit model registration for standalone database commands.

FastAPI imports routes that transitively load every model.  Administrative
scripts do not have that guarantee, so they must load the same registry before
opening an ORM session.
"""

from __future__ import annotations

from importlib import import_module


MODEL_MODULES = (
    "auth_action_token",
    "auth_rate_limit_event",
    "chat",
    "cfb_standing_snapshot",
    "college_team",
    "database_metadata",
    "defense_rating",
    "defense_vs_position",
    "draft",
    "draft_pick",
    "game",
    "game_odds",
    "historical_stats",
    "injury",
    "injury_impact",
    "league",
    "league_invite",
    "league_member",
    "league_message",
    "league_settings",
    "lineup_week_snapshot",
    "matchup",
    "mock_draft",
    "mock_draft_pick",
    "notification",
    "player",
    "player_game_stat",
    "player_role_snapshot",
    "player_season_rank",
    "player_stat",
    "player_waiver_availability",
    "player_week_score",
    "preseason_prior",
    "projection_explanation",
    "projection_input_audit",
    "provider_identity",
    "provider_sync_state",
    "refresh_session",
    "roster",
    "scheduled_notification",
    "scoring_admin_audit",
    "scoring_run",
    "standing",
    "team",
    "team_environment",
    "team_game_stat",
    "team_schedule",
    "team_stats_snapshot",
    "team_week_score",
    "transaction",
    "trade_offer",
    "trade_offer_item",
    "trade_review",
    "usage_share",
    "user",
    "waiver_claim",
    "waiver_claim_audit",
    "waiver_priority",
    "waiver_processing_run",
    "waiver_period",
    "watchlist",
    "weekly_projection",
    "worker_heartbeat",
)


def load_all_models() -> None:
    for module in MODEL_MODULES:
        import_module(f"collegefootballfantasy_api.app.models.{module}")
