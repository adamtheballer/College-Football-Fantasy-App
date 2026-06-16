from __future__ import annotations

from collections import defaultdict, deque
from time import monotonic

from fastapi import HTTPException, Request, status

from api.app.core.config import settings


_failed_login_attempts: dict[str, deque[float]] = defaultdict(deque)


def _client_host(request: Request) -> str:
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _login_key(request: Request, email: str) -> str:
    return f"{_client_host(request)}:{email.strip().lower()}"


def _prune_attempts(attempts: deque[float], now: float, window_seconds: int) -> None:
    cutoff = now - window_seconds
    while attempts and attempts[0] < cutoff:
        attempts.popleft()


def assert_login_not_rate_limited(request: Request, email: str) -> None:
    window_seconds = max(1, settings.auth_failed_login_window_seconds)
    limit = max(1, settings.auth_failed_login_limit)
    now = monotonic()
    attempts = _failed_login_attempts[_login_key(request, email)]
    _prune_attempts(attempts, now, window_seconds)
    if len(attempts) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="too many failed login attempts; try again later",
            headers={"Retry-After": str(window_seconds)},
        )


def record_failed_login(request: Request, email: str) -> None:
    window_seconds = max(1, settings.auth_failed_login_window_seconds)
    now = monotonic()
    attempts = _failed_login_attempts[_login_key(request, email)]
    _prune_attempts(attempts, now, window_seconds)
    attempts.append(now)


def clear_failed_logins(request: Request, email: str) -> None:
    _failed_login_attempts.pop(_login_key(request, email), None)


def reset_auth_rate_limits() -> None:
    _failed_login_attempts.clear()
