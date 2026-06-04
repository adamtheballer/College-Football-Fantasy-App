from __future__ import annotations

import hashlib
import secrets
from urllib.parse import quote, urlparse

from api.app.core.config import settings


LOCALHOST_NAMES = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def _parse_url(value: str):
    candidate = value.strip()
    if not candidate:
        candidate = "http://localhost:5173"
    if "://" not in candidate:
        candidate = f"https://{candidate}"
    return urlparse(candidate)


def normalize_public_web_url() -> str:
    parsed = _parse_url(settings.public_web_url or settings.ui_base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return "http://localhost:5173"
    base = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
    return base or "http://localhost:5173"


def is_localhost_url(url: str) -> bool:
    parsed = _parse_url(url)
    hostname = (parsed.hostname or "").lower()
    return hostname in LOCALHOST_NAMES or hostname.startswith("127.")


def build_mock_draft_invite_link(token: str) -> str:
    encoded_token = quote(token.strip(), safe="")
    return f"{normalize_public_web_url()}/draft/mock/invite/{encoded_token}"


def generate_invite_token() -> str:
    return secrets.token_urlsafe(settings.mock_draft_invite_token_bytes)


def hash_invite_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
