from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_public_web_image_serves_the_built_spa_behind_a_same_origin_api_proxy():
    dockerfile = (REPO_ROOT / "Dockerfile.web").read_text(encoding="utf-8")
    nginx = (REPO_ROOT / "web" / "nginx.conf").read_text(encoding="utf-8")
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    api_client = (REPO_ROOT / "web" / "client" / "lib" / "api.ts").read_text(encoding="utf-8")

    assert "RUN npm run build" in dockerfile
    assert "COPY --from=build /app/web/dist/spa /usr/share/nginx/html" in dockerfile
    assert 'CMD ["nginx", "-g", "daemon off;"]' in dockerfile
    assert "location /api/" in nginx
    assert "resolver 127.0.0.11 valid=10s ipv6=off;" in nginx
    assert "set $api_upstream api:8000;" in nginx
    assert "rewrite ^/api/(.*)$ /$1 break;" in nginx
    assert "proxy_pass http://$api_upstream;" in nginx
    assert "try_files $uri $uri/ /index.html;" in nginx
    assert 'Cache-Control "no-store" always;' in nginx
    assert 'Cache-Control "public, max-age=31536000, immutable" always;' in nginx
    # Docker builds pin this today, but the source fallback must also remain
    # same-origin so a local non-container build cannot silently target a
    # stale host-port API.
    assert 'return "/api";' in api_client
    assert "npm run dev:vite" not in compose
    assert "condition: service_healthy" in compose
    assert "scripts/audit_preseason_source_contract.py --source-dir reports/source-imports/2026" in compose
    assert "CFF_APPLY_PRESEASON_RECONCILIATION" in compose
    assert "scripts/reconcile_preseason_player_data.py" in compose
    assert "scripts/audit_canonical_player_registry.py --source-dir reports/source-imports/2026" in compose
    # The release launcher exports CFF_RUNTIME_MODE. Compose must carry that
    # into Settings as RUNTIME_MODE or a diagnostic launch would falsely
    # identify itself as an unknown/release-like API at /health/runtime.
    assert 'RUNTIME_MODE: "${CFF_RUNTIME_MODE:-unknown}"' in compose
    assert 'PLAYER_HEADSHOTS_ENABLED: "${PLAYER_HEADSHOTS_ENABLED:-false}"' in compose
    assert 'SPORTSDATA_ENABLED: "${SPORTSDATA_ENABLED:-false}"' in compose
    assert 'EMAIL_ENABLED: "${EMAIL_ENABLED:-false}"' in compose
    assert 'PASSWORD_RESET_ENABLED: "${PASSWORD_RESET_ENABLED:-false}"' in compose
    assert 'PASSWORD_RESET_TOKEN_SECRET: "${PASSWORD_RESET_TOKEN_SECRET:-change-me-password-reset-token-secret}"' in compose
    assert 'PUBLIC_WEB_URL: "${PUBLIC_WEB_URL:-}"' in compose
    assert 'RESEND_FROM: "${RESEND_FROM:-}"' in compose
    assert 'SMTP_FROM_EMAIL: "${SMTP_FROM_EMAIL:-}"' in compose
    assert 'location = /.well-known/apple-app-site-association' in nginx
    assert 'default_type application/json;' in nginx
    db_service = re.search(r"^  db:\n(?P<body>.*?)(?=^  [a-z_]+:)", compose, flags=re.MULTILINE | re.DOTALL)
    assert db_service is not None
    assert "restart: unless-stopped" in db_service.group("body")


def test_release_candidate_launcher_is_a_safe_compatibility_shim():
    launcher = (REPO_ROOT / "scripts" / "serve_local_release_candidate.sh").read_text(encoding="utf-8")

    assert "scripts/start-beta-local.sh" in launcher
    assert "cff-rc-" not in launcher
    assert "18000" not in launcher


def test_beta_runtime_scripts_enforce_one_public_origin_and_an_existing_data_volume():
    preflight = (REPO_ROOT / "scripts" / "preflight-beta-local.sh").read_text(encoding="utf-8")
    start = (REPO_ROOT / "scripts" / "start-beta-local.sh").read_text(encoding="utf-8")
    stop = (REPO_ROOT / "scripts" / "stop-beta-local.sh").read_text(encoding="utf-8")
    override = (REPO_ROOT / "docker-compose.beta-local.yml").read_text(encoding="utf-8")

    assert 'EXPECTED_BRANCH="codex/runtime-provenance-contract"' in preflight
    assert 'EXPECTED_PORT="18080"' in preflight
    assert "DISALLOWED_PUBLIC_PORTS=(3000 4173 5173 8000 8001 8080 18000 18081)" in preflight
    assert "check_release_source_integrity.py" in preflight
    assert "git -c core.fsmonitor=false fsck" in preflight
    assert "docker volume inspect" in preflight
    assert "another CFF Compose project is running" in preflight
    assert "VITE_API_BASE_URL must be /api" in preflight
    assert "BETA READY: http://127.0.0.1:18080/" in start
    assert "health/runtime" in start
    assert "down --remove-orphans" in stop
    assert "--volumes" not in stop
    assert "external: true" in override
    assert '"127.0.0.1:18080:8080"' in override
    assert override.count('SPORTSDATA_ENABLED: "false"') == 2
    assert override.count('EMAIL_ENABLED: "false"') == 2
    assert override.count('SCORING_MODE: "disabled"') == 2
    real_stack_runner = (REPO_ROOT / "scripts" / "run_real_stack_e2e.sh").read_text(encoding="utf-8")
    assert 'export EMAIL_ENABLED="${EMAIL_ENABLED:-false}"' in real_stack_runner
    assert 'export ENVIRONMENT="e2e"' in real_stack_runner
    assert 'export E2E_LIFECYCLE_TIME_TRAVEL_ENABLED="true"' in real_stack_runner
    assert '"sportsdata_enabled"] is False' in start
    assert '"email_enabled"] is False' in start
    assert '"provider_polling_expected"] is False' in start
