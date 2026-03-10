from __future__ import annotations

import hashlib
import secrets
from base64 import b64encode, b64decode


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
