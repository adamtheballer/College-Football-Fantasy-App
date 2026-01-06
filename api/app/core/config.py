from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/collegefootballfantasy"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_log_level: str = "info"
    sportsdata_api_key: str | None = None
    sportsdata_base_url: str = "https://api.sportsdata.io/v3/cfb"
    sportsdata_player_stats_path: str = "stats/json/Player/{external_id}"
    sportsdata_player_stats_week_path: str = "stats/json/PlayerGameStatsByWeek/{season}/{week}"
    fantasy_scoring_rules_json: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
