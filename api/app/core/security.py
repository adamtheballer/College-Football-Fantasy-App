from __future__ import annotations

import hmac
import hashlib
import json
import secrets
from base64 import b64decode, b64encode
from datetime import datetime, timedelta, timezone

from collegefootballfantasy_api.app.core.config import settings


def generate_token(length: int = 32) -> str:
    return secrets.token_urlsafe(length)[:length]


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return f"{b64encode(salt).decode()}${b64encode(hashed).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_b64, hash_b64 = stored.split("$", 1)
        salt = b64decode(salt_b64.encode())
        hashed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
        return b64encode(hashed).decode() == hash_b64
    except Exception:
        return False


def generate_invite_code(length: int = 20) -> str:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


class JWTError(ValueError):
    pass


class JWTExpiredError(JWTError):
    pass


def _b64url_encode(value: bytes) -> str:
    return b64encode(value).decode("utf-8").replace("+", "-").replace("/", "_").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return b64decode(padded.replace("-", "+").replace("_", "/"))


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(64)


def create_access_token(*, user_id: int, email: str | None = None) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.jwt_access_token_ttl_minutes)
    payload: dict[str, str | int] = {
        "sub": str(user_id),
        "jti": secrets.token_hex(8),
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    if email:
        payload["email"] = email

    header = {"alg": "HS256", "typ": "JWT"}
    encoded_header = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    encoded_payload = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{encoded_header}.{encoded_payload}".encode("utf-8")
    signature = hmac.new(
        settings.jwt_secret_key.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    encoded_signature = _b64url_encode(signature)
    return f"{encoded_header}.{encoded_payload}.{encoded_signature}", expires_at


def verify_access_token(token: str) -> dict[str, str | int]:
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".", 2)
    except ValueError as exc:  # pragma: no cover - handled by auth errors in runtime
        raise JWTError("invalid access token") from exc

    signing_input = f"{encoded_header}.{encoded_payload}".encode("utf-8")
    expected_signature = hmac.new(
        settings.jwt_secret_key.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    provided_signature = _b64url_decode(encoded_signature)
    if not hmac.compare_digest(provided_signature, expected_signature):
        raise JWTError("invalid access token")

    try:
        payload = json.loads(_b64url_decode(encoded_payload).decode("utf-8"))
    except Exception as exc:  # pragma: no cover - guarded by auth tests
        raise JWTError("invalid access token") from exc

    if not isinstance(payload, dict):
        raise JWTError("invalid access token")

    if "sub" not in payload:
        raise JWTError("invalid access token")

    try:
        exp = int(payload["exp"])
    except Exception as exc:
        raise JWTError("invalid access token") from exc

    now_ts = int(datetime.now(timezone.utc).timestamp())
    if exp <= now_ts:
        raise JWTExpiredError("expired access token")

    return payload
