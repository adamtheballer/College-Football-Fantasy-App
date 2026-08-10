import json
from pathlib import Path
import tomllib

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_vercel_routes_api_before_the_spa_and_strips_the_api_prefix():
    config = json.loads((REPO_ROOT / "web" / "vercel.json").read_text(encoding="utf-8"))

    assert config["$schema"] == "https://openapi.vercel.sh/vercel.json"
    assert config["framework"] == "vite"
    assert config["installCommand"] == "npm ci"
    assert "VERCEL_GIT_COMMIT_SHA" in config["buildCommand"]
    assert 'test -n "$VERCEL_GIT_COMMIT_SHA"' in config["buildCommand"]
    assert config["outputDirectory"] == "dist/spa"
    assert config["rewrites"] == [
        {
            "source": "/api/:path*",
            "destination": "https://api.collegefantasyfootball.org/:path*",
        },
        {"source": "/(.*)", "destination": "/index.html"},
    ]


def test_production_manifest_names_one_canonical_frontend_and_railway_api_contract():
    manifest = yaml.safe_load((REPO_ROOT / "deployments.yaml").read_text(encoding="utf-8"))
    production = manifest["environments"]["production"]
    api = production["api"]
    web = production["web"]

    assert api["railway_config_path"] == "/railway.api.toml"
    assert api["railway_root_directory"] == "/"
    assert api["railway_builder"] == "DOCKERFILE"
    assert api["railway_dockerfile_path"] == "Dockerfile.api"
    assert api["port_env"] == "PORT"
    assert api["start_command"] == (
        "sh -c 'exec uv run uvicorn collegefootballfantasy_api.app.main:app --host 0.0.0.0 --port \"$PORT\"'"
    )
    assert api["migrate_command"] == "PYTHONPATH=. uv run alembic -c api/alembic.ini upgrade head"
    assert api["verify_migrations_command"] == "PYTHONPATH=. uv run python scripts/check_alembic_head.py"
    assert api["railway_predeploy_command"] == (
        "sh -c 'uv run alembic -c api/alembic.ini upgrade head "
        "&& uv run python scripts/check_alembic_head.py'"
    )

    assert web["canonical_project"] == "college-football-fantasy-app"
    assert web["legacy_project_to_disable_manually"] == "college-fantasy-roster"
    assert web["production_branch"] == "main"
    assert web["root_directory"] == "web"
    assert web["production_url"] == "https://www.collegefantasyfootball.org"
    assert web["api_proxy_origin"] == "https://api.collegefantasyfootball.org"
    assert web["required_vercel_system_environment_variables"] == ["VERCEL_GIT_COMMIT_SHA"]


def test_railway_api_config_runs_one_atomic_migration_gate_before_readiness():
    config = tomllib.loads((REPO_ROOT / "railway.api.toml").read_text(encoding="utf-8"))

    assert config["build"] == {"builder": "DOCKERFILE", "dockerfilePath": "Dockerfile.api"}
    assert config["deploy"]["preDeployCommand"] == [
        "sh -c 'uv run alembic -c api/alembic.ini upgrade head "
        "&& uv run python scripts/check_alembic_head.py'"
    ]
    start_command = config["deploy"]["startCommand"]
    assert start_command == (
        "sh -c 'exec uv run uvicorn collegefootballfantasy_api.app.main:app --host 0.0.0.0 --port \"$PORT\"'"
    )
    assert not start_command.startswith("PYTHONPATH=.")
    assert "sh -c" in start_command
    assert "exec uv run uvicorn" in start_command
    assert "--host 0.0.0.0" in start_command
    assert '"$PORT"' in start_command
    assert config["deploy"]["healthcheckPath"] == "/health/ready"
    assert config["deploy"]["healthcheckTimeout"] == 100
    assert config["deploy"]["restartPolicyType"] == "ALWAYS"


def test_runtime_proxy_verifier_rejects_html_and_checks_the_browser_api_surface():
    verifier = (REPO_ROOT / "web" / "scripts" / "verify-runtime-proxy.mjs").read_text(encoding="utf-8")

    assert "not JSON" in verifier
    assert '"/api/health"' in verifier
    assert '"/api/health/runtime"' in verifier
    assert '"/api/health/ready"' in verifier
    assert '"/api/players?limit=1&offset=0"' in verifier
    assert '"/api/projections?season=2026&week=1&limit=1&offset=0"' in verifier
    assert '"Browser schedule channel"' in verifier
    assert '"/api/auth/me"' in verifier
    assert '"/api/saturday-pick-6/current?season=2026&week=1"' in verifier
    assert "DIRECT_API_RUNTIME_URL" in verifier
