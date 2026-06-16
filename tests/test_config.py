import pytest

from api.app import main
from api.app.core.config import Settings


def test_cors_origin_list_parses_csv():
    settings = Settings(cors_origins="http://localhost:8080, http://127.0.0.1:8080,,")

    assert settings.cors_origin_list == ["http://localhost:8080", "http://127.0.0.1:8080"]


def test_production_rejects_default_jwt_secret():
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        Settings(environment="production", jwt_secret_key="change-me-in-production")


def test_development_allows_default_jwt_secret():
    settings = Settings(environment="development", jwt_secret_key="change-me-in-production")

    assert settings.jwt_secret_key == "change-me-in-production"


def test_build_cors_origins_uses_configured_origins(monkeypatch):
    monkeypatch.setattr(main.settings, "cors_origins", "https://app.example.com")
    monkeypatch.setattr(main.settings, "ui_base_url", "")
    monkeypatch.setattr(main.settings, "public_web_url", "")

    assert main.build_cors_origins() == ["https://app.example.com"]
