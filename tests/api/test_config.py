import pytest
from pydantic import ValidationError

from collegefootballfantasy_api.app.core.config import (
    DEFAULT_CORS_ORIGIN_REGEX,
    DEFAULT_CORS_ORIGINS,
    DEFAULT_JWT_SECRET_KEY,
    Settings,
)


def make_settings(**overrides):
    defaults = {
        "_env_file": None,
        "environment": "development",
        "jwt_secret_key": DEFAULT_JWT_SECRET_KEY,
        "cors_origins": DEFAULT_CORS_ORIGINS,
        "cors_origin_regex": DEFAULT_CORS_ORIGIN_REGEX,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def test_development_allows_local_default_cors_and_jwt_secret():
    settings = make_settings()

    assert settings.environment == "development"
    assert settings.jwt_secret_key == DEFAULT_JWT_SECRET_KEY
    assert "http://localhost:5173" in settings.allowed_cors_origins
    assert settings.email_verification_required is False


def test_development_can_require_email_verification_when_enabled():
    settings = make_settings(auth_require_email_verification=True)

    assert settings.email_verification_required is True


def test_production_rejects_default_jwt_secret():
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY must be changed"):
        make_settings(
            environment="production",
            cors_origins="https://app.example.com",
            cors_origin_regex=None,
        )


def test_production_rejects_default_localhost_cors_origins():
    with pytest.raises(ValidationError, match="CORS_ORIGINS must be explicitly set"):
        make_settings(
            environment="production",
            jwt_secret_key="safe-production-secret",
            cors_origin_regex=None,
        )


def test_production_rejects_localhost_cors_origin():
    with pytest.raises(ValidationError, match="cannot contain localhost"):
        make_settings(
            environment="production",
            jwt_secret_key="safe-production-secret",
            cors_origins="https://app.example.com,http://localhost:5173",
            cors_origin_regex=None,
        )


def test_production_rejects_wildcard_cors_origin():
    with pytest.raises(ValidationError, match="cannot contain '\\*'"):
        make_settings(
            environment="production",
            jwt_secret_key="safe-production-secret",
            cors_origins="*",
            cors_origin_regex=None,
        )


def test_production_rejects_default_localhost_cors_regex():
    with pytest.raises(ValidationError, match="CORS_ORIGIN_REGEX must be unset"):
        make_settings(
            environment="production",
            jwt_secret_key="safe-production-secret",
            cors_origins="https://app.example.com",
        )


def test_production_accepts_explicit_safe_cors_and_jwt_secret():
    settings = make_settings(
        environment="production",
        jwt_secret_key="safe-production-secret",
        cors_origins="https://app.example.com,https://www.example.com",
        cors_origin_regex=None,
        refresh_cookie_secure=True,
        email_delivery_mode="smtp",
        smtp_host="smtp.example.com",
        smtp_from_email="noreply@example.com",
    )

    assert settings.is_production
    assert settings.allowed_cors_origins == ["https://app.example.com", "https://www.example.com"]
    assert settings.email_verification_required is True


def test_blank_cors_origin_regex_disables_regex_for_production():
    settings = make_settings(
        environment="production",
        jwt_secret_key="safe-production-secret",
        cors_origins="https://app.example.com",
        cors_origin_regex="",
        refresh_cookie_secure=True,
        email_delivery_mode="smtp",
        smtp_host="smtp.example.com",
        smtp_from_email="noreply@example.com",
    )

    assert settings.allowed_cors_origin_regex is None


def test_production_rejects_console_email_delivery_mode():
    with pytest.raises(ValidationError, match="EMAIL_DELIVERY_MODE=console is not allowed"):
        make_settings(
            environment="production",
            jwt_secret_key="safe-production-secret",
            cors_origins="https://app.example.com",
            cors_origin_regex=None,
            refresh_cookie_secure=True,
            email_delivery_mode="console",
        )


def test_production_rejects_insecure_refresh_cookie():
    with pytest.raises(ValidationError, match="REFRESH_COOKIE_SECURE must be true"):
        make_settings(
            environment="production",
            jwt_secret_key="safe-production-secret",
            cors_origins="https://app.example.com",
            cors_origin_regex=None,
            refresh_cookie_secure=False,
        )
