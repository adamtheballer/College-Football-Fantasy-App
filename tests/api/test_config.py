import pytest
from pydantic import ValidationError

from collegefootballfantasy_api.app.core.config import (
    DEFAULT_BETA_ACCESS_RESERVATION_SECRET,
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


def production_required_settings() -> dict[str, object]:
    return {
        "ui_base_url": "https://app.example.com",
        "email_enabled": True,
        "email_delivery_mode": "smtp",
        "smtp_host": "smtp.example.com",
        "smtp_from_email": "no-reply@example.com",
        "smtp_use_tls": True,
        "support_email": "support@example.com",
        "privacy_policy_url": "https://app.example.com/privacy",
        "terms_url": "https://app.example.com/terms",
        "provider_disclosure_url": "https://app.example.com/provider-disclosure",
        "sportsdata_enabled": True,
        "sportsdata_api_key": "sportsdata-production-key",
    }


def test_development_allows_local_default_cors_and_jwt_secret():
    settings = make_settings()

    assert settings.environment == "development"
    assert settings.jwt_secret_key == DEFAULT_JWT_SECRET_KEY
    assert "http://localhost:5173" in settings.allowed_cors_origins


@pytest.mark.parametrize("value", ("false", "0", "no", "off"))
def test_sportsdata_false_environment_forms_disable_provider(value):
    settings = make_settings(sportsdata_enabled=value)

    assert settings.sportsdata_enabled is False
    assert settings.provider_polling_expected is False


def test_sportsdata_true_environment_form_enables_provider_only_when_explicit():
    settings = make_settings(sportsdata_enabled="true")

    assert settings.sportsdata_enabled is True


def test_sportsdata_defaults_to_disabled_without_an_environment_value():
    settings = make_settings()

    assert settings.sportsdata_enabled is False
    assert settings.provider_polling_expected is False


def test_beta_access_rejects_default_or_short_hmac_secrets_in_every_environment():
    with pytest.raises(ValidationError, match="BETA_ACCESS_CODE_HMAC_SECRET must be changed"):
        make_settings(beta_access_enabled=True)

    with pytest.raises(ValidationError, match="BETA_ACCESS_RESERVATION_SECRET must be changed"):
        make_settings(
            beta_access_enabled=True,
            beta_access_code_hmac_secret="x" * 32,
            beta_access_reservation_secret=DEFAULT_BETA_ACCESS_RESERVATION_SECRET,
        )

    with pytest.raises(ValidationError, match="at least 32 characters"):
        make_settings(
            beta_access_enabled=True,
            beta_access_code_hmac_secret="short",
            beta_access_reservation_secret="also-short",
        )


def test_beta_access_accepts_nondefault_development_secrets():
    settings = make_settings(
        beta_access_enabled=True,
        beta_access_code_hmac_secret="c" * 32,
        beta_access_reservation_secret="r" * 32,
    )

    assert settings.beta_access_enabled


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
        **production_required_settings(),
    )

    assert settings.is_production
    assert settings.allowed_cors_origins == ["https://app.example.com", "https://www.example.com"]


def test_blank_cors_origin_regex_disables_regex_for_production():
    settings = make_settings(
        environment="production",
        jwt_secret_key="safe-production-secret",
        cors_origins="https://app.example.com",
        cors_origin_regex="",
        refresh_cookie_secure=True,
        **production_required_settings(),
    )

    assert settings.allowed_cors_origin_regex is None


def test_production_rejects_insecure_refresh_cookie():
    with pytest.raises(ValidationError, match="REFRESH_COOKIE_SECURE must be true"):
        make_settings(
            environment="production",
            jwt_secret_key="safe-production-secret",
            cors_origins="https://app.example.com",
            cors_origin_regex=None,
            refresh_cookie_secure=False,
            **production_required_settings(),
        )


def test_production_allows_beta_without_smtp_or_public_policy_urls():
    settings = make_settings(
        environment="production",
        jwt_secret_key="safe-production-secret",
        cors_origins="https://app.example.com",
        cors_origin_regex=None,
        refresh_cookie_secure=True,
        ui_base_url="https://app.example.com",
        scoring_mode="disabled",
        sportsdata_enabled=False,
        email_enabled=False,
    )

    assert settings.email_enabled is False
    assert settings.smtp_host is None
    assert settings.support_email is None
    assert settings.privacy_policy_url is None


@pytest.mark.parametrize("value", ("false", "0", "no", "off"))
def test_email_false_environment_forms_disable_delivery(value):
    assert make_settings(email_enabled=value).email_enabled is False


def test_email_true_environment_form_enables_delivery_only_when_explicit():
    assert make_settings(email_enabled="true").email_enabled is True


def test_email_defaults_to_disabled_without_an_environment_value():
    assert make_settings().email_enabled is False


def test_production_email_enabled_requires_smtp_sender():
    required = production_required_settings()
    required.pop("smtp_host")
    with pytest.raises(ValidationError, match="SMTP_HOST and SMTP_FROM_EMAIL are required"):
        make_settings(
            environment="production",
            jwt_secret_key="safe-production-secret",
            cors_origins="https://app.example.com",
            cors_origin_regex=None,
            refresh_cookie_secure=True,
            **required,
        )


def test_production_rejects_console_email_delivery():
    with pytest.raises(ValidationError, match="EMAIL_DELIVERY_MODE must be smtp"):
        make_settings(
            environment="production",
            jwt_secret_key="safe-production-secret",
            cors_origins="https://app.example.com",
            cors_origin_regex=None,
            refresh_cookie_secure=True,
            **{
                key: value
                for key, value in production_required_settings().items()
                if key not in {"email_delivery_mode"}
            },
        )


def test_email_delivery_mode_rejects_unknown_value():
    with pytest.raises(ValidationError, match="EMAIL_DELIVERY_MODE must be one of"):
        make_settings(email_delivery_mode="resend")


def test_production_rejects_non_https_or_local_ui_base_url():
    required = production_required_settings()
    required["ui_base_url"] = "http://localhost:8080"
    with pytest.raises(ValidationError, match="UI_BASE_URL must be a non-local HTTPS URL"):
        make_settings(
            environment="production",
            jwt_secret_key="safe-production-secret",
            cors_origins="https://app.example.com",
            cors_origin_regex=None,
            refresh_cookie_secure=True,
            **required,
        )


def test_production_rejects_missing_sportsdata_credentials():
    required = production_required_settings()
    required.pop("sportsdata_api_key")
    with pytest.raises(ValidationError, match="SPORTSDATA_ENABLED=true and SPORTSDATA_API_KEY"):
        make_settings(
            environment="production",
            jwt_secret_key="safe-production-secret",
            cors_origins="https://app.example.com",
            cors_origin_regex=None,
            refresh_cookie_secure=True,
            **required,
        )


def test_production_allows_scoring_disabled_without_sportsdata_credentials():
    required = production_required_settings()
    required.pop("sportsdata_api_key")
    required["sportsdata_enabled"] = False

    settings = make_settings(
        environment="production",
        jwt_secret_key="safe-production-secret",
        cors_origins="https://app.example.com",
        cors_origin_regex=None,
        refresh_cookie_secure=True,
        scoring_mode="disabled",
        **required,
    )

    assert settings.scoring_enabled is False
    assert settings.scoring_worker_expected is False
    assert settings.provider_polling_expected is False


def test_production_rejects_provider_enablement_when_scoring_is_disabled():
    with pytest.raises(ValidationError, match="SPORTSDATA_ENABLED must be false"):
        make_settings(
            environment="production",
            jwt_secret_key="safe-production-secret",
            cors_origins="https://app.example.com",
            cors_origin_regex=None,
            refresh_cookie_secure=True,
            scoring_mode="disabled",
            **production_required_settings(),
        )


def test_production_rejects_insecure_smtp():
    required = production_required_settings()
    required["smtp_use_tls"] = False
    with pytest.raises(ValidationError, match="SMTP_USE_TLS must be true"):
        make_settings(
            environment="production",
            jwt_secret_key="safe-production-secret",
            cors_origins="https://app.example.com",
            cors_origin_regex=None,
            refresh_cookie_secure=True,
            **required,
        )


def test_production_rejects_unofficial_scoring_provider_without_override():
    with pytest.raises(ValidationError, match="Unofficial SCORING_PROVIDER"):
        make_settings(
            environment="production",
            jwt_secret_key="safe-production-secret",
            cors_origins="https://app.example.com",
            cors_origin_regex=None,
            refresh_cookie_secure=True,
            scoring_provider="espn",
            **production_required_settings(),
        )


def test_production_allows_unofficial_scoring_provider_only_with_explicit_override():
    settings = make_settings(
        environment="production",
        jwt_secret_key="safe-production-secret",
        cors_origins="https://app.example.com",
        cors_origin_regex=None,
        refresh_cookie_secure=True,
        scoring_provider="espn",
        scoring_allow_unofficial_providers=True,
        **production_required_settings(),
    )

    assert settings.scoring_provider == "espn"
