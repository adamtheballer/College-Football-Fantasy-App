from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_public_web_image_serves_the_built_spa_behind_a_same_origin_api_proxy():
    dockerfile = (REPO_ROOT / "Dockerfile.web").read_text(encoding="utf-8")
    nginx = (REPO_ROOT / "web" / "nginx.conf").read_text(encoding="utf-8")
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "RUN npm run build" in dockerfile
    assert "COPY --from=build /app/web/dist/spa /usr/share/nginx/html" in dockerfile
    assert 'CMD ["nginx", "-g", "daemon off;"]' in dockerfile
    assert "location /api/" in nginx
    assert "proxy_pass http://api:8000/;" in nginx
    assert "try_files $uri $uri/ /index.html;" in nginx
    assert "npm run dev:vite" not in compose
    assert "condition: service_healthy" in compose
    assert "scripts/audit_preseason_source_contract.py --source-dir reports/source-imports/2026" in compose
    assert "scripts/bootstrap_canonical_player_data.py --apply" in compose
    assert "scripts/audit_canonical_player_registry.py --source-dir reports/source-imports/2026" in compose


def test_release_candidate_launcher_embeds_the_checked_out_revision_and_refuses_dirty_source():
    launcher = (REPO_ROOT / "scripts" / "serve_local_release_candidate.sh").read_text(encoding="utf-8")

    assert 'CFF_GIT_SHA="$(git rev-parse HEAD)"' in launcher
    assert 'CFF_GIT_BRANCH="$(git branch --show-current)"' in launcher
    assert 'git status --porcelain --untracked-files=normal' in launcher
    assert 'ALLOW_DIRTY_RELEASE_CANDIDATE:-false' in launcher
    assert "Refusing to label a dirty worktree as a release candidate." in launcher
    assert "scripts/check_release_source_integrity.py" in launcher
    assert "scripts/audit_preseason_source_contract.py" in launcher
    assert "docker compose up --build --detach db api web lifecycle_worker" in launcher
    assert 'export API_PORT="${API_PORT:-8000}"' in launcher
    assert '"http://127.0.0.1:${API_PORT}/health/runtime"' in launcher
