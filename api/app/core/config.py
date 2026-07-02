from pathlib import Path

from pydantic import model_validator
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
    fantasy_scoring_rules_json: str | None = None
    jwt_secret_key: str = DEFAULT_JWT_SECRET_KEY
    jwt_access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 14
    refresh_cookie_name: str = "cfb_refresh_token"
    refresh_cookie_secure: bool = False
    refresh_cookie_samesite: str = "lax"
    refresh_cookie_domain: str | None = None
    allow_legacy_api_token_auth: bool = False

    model_config = SettingsConfigDict(
        env_file=(str(PROJECT_ROOT / ".env"), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

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

        return self


settings = Settings()
