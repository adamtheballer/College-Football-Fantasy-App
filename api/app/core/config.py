from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    environment: str = "development"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5433/collegefootballfantasy"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_log_level: str = "info"
    ui_base_url: str = "http://localhost:8080"
    public_web_url: str = "http://localhost:8080"
    public_api_url: str = "http://localhost:8000"
    api_public_mode: bool = False
    mock_draft_invite_token_bytes: int = 24
    mock_draft_invite_token_ttl_days: int = 7
    mock_draft_unsent_retention_hours: int = 24
    mock_draft_emailed_retention_days: int = 30
    cors_origins: str = "http://localhost:8080,http://127.0.0.1:8080"
    cfbd_api_key: str | None = None
    cfbd_base_url: str = "https://api.collegefootballdata.com"
    resend_api_key: str | None = None
    odds_api_key: str | None = None
    odds_base_url: str = "https://api.the-odds-api.com/v4"
    sportsdata_api_key: str | None = None
    sportsdata_base_url: str = "https://api.sportsdata.io/v3/cfb"
    sportsdata_enabled: bool = True
    sportsdata_player_stats_path: str = "stats/json/Player/{external_id}"
    sportsdata_player_stats_week_path: str = "stats/json/PlayerGameStatsByWeek/{season}/{week}"
    sportsdata_players_path: str = "scores/json/Players"
    sportsdata_schedule_season_path: str = "scores/json/Games/{season}"
    sportsdata_standings_path: str = "scores/json/Standings/{season}"
    sportsdata_team_season_stats_path: str = "scores/json/TeamSeasonStats/{season}"
    sportsdata_injuries_season_path: str = "scores/json/Injuries/{season}"
    sportsdata_injured_players_path: str = "scores/json/InjuredPlayers"
    sportsdata_cache_ttl_days: int = 30
    sportsdata_reference_ttl_days: int = 30
    sportsdata_schedule_ttl_days: int = 30
    sportsdata_standings_ttl_days: int = 30
    sportsdata_injury_ttl_days: int = 30
    provider_default_cache_ttl_days: int = 30
    fantasy_scoring_rules_json: str | None = None
    jwt_secret_key: str = "change-me-in-production"
    jwt_access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 14
    refresh_cookie_name: str = "cfb_refresh_token"
    refresh_cookie_secure: bool = False
    refresh_cookie_samesite: str = "lax"
    refresh_cookie_domain: str | None = None
    allow_legacy_api_token_auth: bool = False
    realtime_relay_enabled: bool = True
    realtime_relay_poll_interval_ms: int = 350
    realtime_relay_batch_size: int = 200
    realtime_relay_start_from_latest: bool = True
    realtime_immediate_broadcast_enabled: bool = False
    draft_timeout_runner_enabled: bool = True
    draft_timeout_runner_interval_ms: int = 1000
    draft_timeout_batch_limit: int = 200
    draft_autopick_delay_seconds: int = 3
    web_push_vapid_public_key: str | None = None
    web_push_vapid_private_key: str | None = None
    web_push_vapid_subject: str | None = None

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def model_post_init(self, __context: object) -> None:
        if self.environment.lower() == "production" and self.jwt_secret_key == "change-me-in-production":
            raise RuntimeError("JWT_SECRET_KEY must be set to a secure value when ENVIRONMENT=production.")

    model_config = SettingsConfigDict(
        env_file=(str(PROJECT_ROOT / ".env"), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
