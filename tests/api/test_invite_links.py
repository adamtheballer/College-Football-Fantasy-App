from api.app.core.config import settings
from api.app.main import build_cors_origins
from api.app.services.invite_links import (
    build_mock_draft_invite_link,
    generate_invite_token,
    hash_invite_token,
    is_localhost_url,
)


def test_build_mock_draft_invite_link_uses_public_web_url(monkeypatch):
    monkeypatch.setattr(settings, "public_web_url", "https://draft-tunnel.example/")

    assert build_mock_draft_invite_link("secure-token") == "https://draft-tunnel.example/draft/mock/invite/secure-token"


def test_localhost_public_web_url_produces_local_invite_link(monkeypatch):
    monkeypatch.setattr(settings, "public_web_url", "http://localhost:5173")

    link = build_mock_draft_invite_link("local-token")

    assert link == "http://localhost:5173/draft/mock/invite/local-token"
    assert is_localhost_url(link) is True


def test_public_web_url_produces_public_invite_link(monkeypatch):
    monkeypatch.setattr(settings, "public_web_url", "https://college-football-dev.example")

    link = build_mock_draft_invite_link("public-token")

    assert link == "https://college-football-dev.example/draft/mock/invite/public-token"
    assert is_localhost_url(link) is False


def test_cors_origin_builder_includes_public_web_url_origin(monkeypatch):
    monkeypatch.setattr(settings, "ui_base_url", "https://ui-base.example/path")
    monkeypatch.setattr(settings, "public_web_url", "https://frontend-tunnel.example/draft")

    origins = build_cors_origins()

    assert "http://localhost:5173" in origins
    assert "http://127.0.0.1:5175" in origins
    assert "https://ui-base.example" in origins
    assert "https://frontend-tunnel.example" in origins
    assert "*" not in origins


def test_invite_token_generation_and_hash_are_stable():
    token = generate_invite_token()

    assert len(token) >= 24
    assert hash_invite_token("same-token") == hash_invite_token("same-token")
    assert hash_invite_token("same-token") != hash_invite_token("other-token")
