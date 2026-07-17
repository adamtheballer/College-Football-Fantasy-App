from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_JWT_SECRET_KEY = "change-me-in-production"
DEFAULT_CORS_ORIGINS = (
    "http://localhost:5173,"
    "http://127.0.0.1:5173,"
    "http://localhost:5174,"
    "http://127.0.0.1:5174,"
    "http://localhost:8080,"
    "http://127.0.0.1:8080"
)
DEFAULT_CORS_ORIGIN_REGEX = r"https?://(localhost|127\.0\.0\.1):[0-9]+"


class Settings(BaseSettings):
    environment: str = "development"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5433/collegefootballfantasy"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_log_level: str = "info"
    ui_base_url: str = "http://localhost:5173"
    cors_origins: str = DEFAULT_CORS_ORIGINS
    cors_origin_regex: str | None = DEFAULT_CORS_ORIGIN_REGEX
    cfbd_api_key: str | None = None
    cfbd_base_url: str = "https://api.collegefootballdata.com"
    resend_api_key: str | None = None
    odds_api_key: str | None = None
    odds_base_url: str = "https://api.the-odds-api.com/v4"
    sportsdata_api_key: str | None = None
    sportsdata_base_url: str = "https://api.sportsdata.io/v3/cfb"
    sportsdataio_api_key: str | None = None
    scoring_provider: str = "sportsdata"
    scoring_allow_unofficial_providers: bool = False
    scoring_worker_interval_live_seconds: int = 60
    scoring_worker_interval_postgame_seconds: int = 900
    scoring_worker_interval_correction_seconds: int = 3600
    scoring_worker_retry_max_attempts: int = 3
    scoring_worker_retry_base_seconds: int = 5
    lifecycle_worker_interval_seconds: int = 5
    draft_cpu_pick_delay_seconds: int = 4
    scoring_dead_letter_after_failures: int = 3
    provider_unmatched_failure_threshold_percent: float = 10.0
    projection_provider: str = "sportsdataio"
    sportsdata_enabled: bool = True
    sportsdata_player_stats_path: str = "stats/json/Player/{external_id}"
    sportsdata_player_stats_week_path: str = "stats/json/PlayerGameStatsByWeek/{season}/{week}"
    sportsdata_players_path: str = "scores/json/Players"
    sportsdata_schedule_season_path: str = "scores/json/Games/{season}"
    sportsdata_standings_path: str = "scores/json/Standings/{season}"
    sportsdata_injuries_season_path: str = "scores/json/Injuries/{season}"
    sportsdata_cache_ttl_days: int = 30
    sportsdata_reference_ttl_days: int = 30
    sportsdata_schedule_ttl_days: int = 30
    sportsdata_standings_ttl_days: int = 30
    sportsdata_injury_ttl_days: int = 30
    provider_default_cache_ttl_days: int = 30
    historical_stats_provider: str = "espn"
    espn_historical_stats_enabled: bool = False
    espn_historical_stats_base_url: str = (
        "https://site.web.api.espn.com/apis/common/v3/sports/football/college-football"
    )
    espn_historical_stats_timeout_seconds: int = 10
    espn_historical_stats_max_retries: int = 3
    espn_historical_stats_requests_per_second: float = 1.0
    espn_historical_stats_cache_ttl_days: int = 30
    espn_historical_stats_seasons_back: int = 4
    espn_historical_stats_user_agent: str = "CollegeFootballFantasy/0.1 historical-stats"
    espn_historical_stats_fail_open: bool = True
    player_card_historical_stats_enabled: bool = True
    fantasy_scoring_rules_json: str | None = None
    jwt_secret_key: str = DEFAULT_JWT_SECRET_KEY
    jwt_access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 14
    refresh_cookie_name: str = "cfb_refresh_token"
    refresh_cookie_secure: bool = False
    refresh_cookie_samesite: str = "lax"
    refresh_cookie_domain: str | None = None
    allow_legacy_api_token_auth: bool = False
    auth_password_reset_ttl_minutes: int = 30
    auth_failed_login_limit: int = 5
    auth_failed_login_window_minutes: int = 15
    auth_lockout_minutes: int = 15
    auth_rate_limit_window_minutes: int = 15
    auth_signup_rate_limit: int = 5
    auth_login_rate_limit: int = 10
    auth_refresh_rate_limit: int = 30
    auth_password_reset_rate_limit: int = 5
    provider_refresh_rate_limit: int = 30
    chat_message_rate_limit: int = 30
    chat_message_rate_limit_window_minutes: int = 1
    chat_message_sustained_rate_limit: int = 120
    chat_message_sustained_rate_limit_window_minutes: int = 15
    chat_direct_thread_rate_limit: int = 20
    chat_direct_thread_rate_limit_window_minutes: int = 60
    chat_read_rate_limit: int = 120
    chat_read_rate_limit_window_minutes: int = 1
    chat_edit_window_minutes: int = 15
    email_delivery_mode: str = "console"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None
    smtp_use_tls: bool = True
    support_email: str | None = None
    privacy_policy_url: str | None = None
    terms_url: str | None = None
    provider_disclosure_url: str | None = None
    security_headers_enabled: bool = True

    model_config = SettingsConfigDict(
        env_file=(str(PROJECT_ROOT / ".env"), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("draft_cpu_pick_delay_seconds")
    @classmethod
    def validate_draft_cpu_pick_delay_seconds(cls, value: int) -> int:
        if value < 2 or value > 8:
            raise ValueError("DRAFT_CPU_PICK_DELAY_SECONDS must be between 2 and 8")
        return value

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() == "production"

    @property
    def allowed_cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def allowed_cors_origin_regex(self) -> str | None:
        if self.cors_origin_regex is None:
            return None
        normalized = self.cors_origin_regex.strip()
        return normalized or None

    @staticmethod
    def _is_local_origin(origin: str) -> bool:
        normalized = origin.strip().lower()
        return "localhost" in normalized or "127.0.0.1" in normalized or "0.0.0.0" in normalized

    @model_validator(mode="after")
    def validate_production_safety(self) -> "Settings":
        if not self.is_production:
            return self

        if self.jwt_secret_key == DEFAULT_JWT_SECRET_KEY:
            raise ValueError("JWT_SECRET_KEY must be changed when ENVIRONMENT=production")

        if not self.allowed_cors_origins:
            raise ValueError("CORS_ORIGINS must contain at least one production web origin")

        if self.cors_origins == DEFAULT_CORS_ORIGINS:
            raise ValueError("CORS_ORIGINS must be explicitly set when ENVIRONMENT=production")

        if any(origin == "*" for origin in self.allowed_cors_origins):
            raise ValueError("CORS_ORIGINS cannot contain '*' when ENVIRONMENT=production")

        if any(self._is_local_origin(origin) for origin in self.allowed_cors_origins):
            raise ValueError("CORS_ORIGINS cannot contain localhost origins when ENVIRONMENT=production")

        if self.cors_origin_regex == DEFAULT_CORS_ORIGIN_REGEX:
            raise ValueError("CORS_ORIGIN_REGEX must be unset or production-safe when ENVIRONMENT=production")

        if self.allowed_cors_origin_regex and self._is_local_origin(self.allowed_cors_origin_regex):
            raise ValueError("CORS_ORIGIN_REGEX cannot allow localhost when ENVIRONMENT=production")

        if not self.refresh_cookie_secure:
            raise ValueError("REFRESH_COOKIE_SECURE must be true when ENVIRONMENT=production")

        if self.email_delivery_mode.strip().lower() == "console":
            raise ValueError("EMAIL_DELIVERY_MODE cannot be console when ENVIRONMENT=production")

        if self.email_delivery_mode.strip().lower() == "smtp" and (
            not self.smtp_host or not self.smtp_from_email
        ):
            raise ValueError("SMTP_HOST and SMTP_FROM_EMAIL are required when ENVIRONMENT=production")

        if not self.support_email:
            raise ValueError("SUPPORT_EMAIL is required when ENVIRONMENT=production")

        if not self.privacy_policy_url:
            raise ValueError("PRIVACY_POLICY_URL is required when ENVIRONMENT=production")

        if not self.terms_url:
            raise ValueError("TERMS_URL is required when ENVIRONMENT=production")

        if not self.provider_disclosure_url:
            raise ValueError("PROVIDER_DISCLOSURE_URL is required when ENVIRONMENT=production")

        if self.scoring_provider.strip().lower() in {"espn", "cache", "mock"} and not self.scoring_allow_unofficial_providers:
            raise ValueError("Unofficial SCORING_PROVIDER requires SCORING_ALLOW_UNOFFICIAL_PROVIDERS=true")

        if self.scoring_worker_interval_live_seconds < 30:
            raise ValueError("SCORING_WORKER_INTERVAL_LIVE_SECONDS must be at least 30 in production")

        return self


settings = Settings()
