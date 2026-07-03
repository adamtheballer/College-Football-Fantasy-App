from __future__ import annotations

import hmac
import hashlib
import json
import secrets
from base64 import b64decode, b64encode
from binascii import Error as Base64DecodeError
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from collegefootballfantasy_api.app.core.config import settings

PASSWORD_HASH_ALGORITHM = "argon2id"
ARGON2_HASH_PREFIX = f"{PASSWORD_HASH_ALGORITHM}$"
ARGON2_HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4, hash_len=32, salt_len=16)
PBKDF2_PASSWORD_HASH_ALGORITHM = "pbkdf2_sha256"
LEGACY_PASSWORD_HASH_ITERATIONS = 100_000


def generate_token(length: int = 32) -> str:
    return secrets.token_urlsafe(length)[:length]


def hash_password(password: str) -> str:
    return f"{ARGON2_HASH_PREFIX}{ARGON2_HASHER.hash(password)}"


def _verify_pbkdf2_password(password: str, *, iterations: int, salt_b64: str, hash_b64: str) -> bool:
    salt = b64decode(salt_b64.encode())
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(b64encode(hashed).decode(), hash_b64)


def verify_password(password: str, stored: str) -> bool:
    try:
        if stored.startswith(ARGON2_HASH_PREFIX):
            encoded_hash = stored[len(ARGON2_HASH_PREFIX) :]
            return ARGON2_HASHER.verify(encoded_hash, password)

        parts = stored.split("$")
        if len(parts) == 4 and parts[0] == PBKDF2_PASSWORD_HASH_ALGORITHM:
            _, iterations_raw, salt_b64, hash_b64 = parts
            iterations = int(iterations_raw)
        elif len(parts) == 2:
            salt_b64, hash_b64 = parts
            iterations = LEGACY_PASSWORD_HASH_ITERATIONS
        else:
            return False

        return _verify_pbkdf2_password(password, iterations=iterations, salt_b64=salt_b64, hash_b64=hash_b64)
    except (InvalidHashError, VerificationError, VerifyMismatchError, ValueError, Base64DecodeError):
        return False


def needs_password_rehash(stored: str) -> bool:
    try:
        if not stored.startswith(ARGON2_HASH_PREFIX):
            return True
        return ARGON2_HASHER.check_needs_rehash(stored[len(ARGON2_HASH_PREFIX) :])
    except (InvalidHashError, VerificationError, ValueError):
        return True


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
