from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_production_manifest_covers_runtime_startup_requirements():
    manifest = yaml.safe_load((PROJECT_ROOT / "deployments.yaml").read_text())
    production = manifest["environments"]["production"]
    required_env = set(production["required_env"])

    assert {
        "DATABASE_URL",
        "ENVIRONMENT",
        "JWT_SECRET_KEY",
        "CORS_ORIGINS",
        "UI_BASE_URL",
        "PUBLIC_API_BASE_URL",
        "VITE_API_BASE_URL",
        "REFRESH_COOKIE_SECURE",
        "EMAIL_DELIVERY_MODE",
        "SMTP_HOST",
        "SMTP_FROM_EMAIL",
        "SMTP_USE_TLS",
        "SUPPORT_EMAIL",
        "PRIVACY_POLICY_URL",
        "TERMS_URL",
        "PROVIDER_DISCLOSURE_URL",
        "SCORING_PROVIDER",
        "SPORTSDATA_API_KEY",
        "SPORTSDATA_ENABLED",
        "SCORING_SEASON",
        "SCORING_WEEK",
    }.issubset(required_env)

    safety_gates = production["safety_gates"]
    assert safety_gates["environment_must_equal"] == "production"
    assert safety_gates["ui_base_url_must_be_non_local_https"] is True
    assert safety_gates["email_delivery_must_be_smtp"] is True
    assert safety_gates["smtp_tls_must_be_true"] is True
    assert safety_gates["sportsdata_credentials_required"] is True


def test_production_manifest_starts_required_lifecycle_workers_before_promotion():
    manifest = yaml.safe_load((PROJECT_ROOT / "deployments.yaml").read_text())
    production = manifest["environments"]["production"]

    assert production["api"]["promotion_order"] == [
        "build_artifact",
        "verify_release_source_artifact",
        "validate_immutable_player_snapshot",
        "run_database_migrations",
        "verify_alembic_head",
        "bootstrap_canonical_player_registry",
        "verify_canonical_player_registry",
        "start_or_promote_api",
        "require_health_ready",
    ]
    assert production["release_source"]["canonical_id_owner"] == "application_database_players_id"
    assert production["release_source"]["source_snapshot_directory"] == "reports/source-imports/2026"
    assert production["workers"]["scoring_processor"]["enabled"] is True
    assert production["workers"]["lifecycle_processor"]["enabled"] is True
