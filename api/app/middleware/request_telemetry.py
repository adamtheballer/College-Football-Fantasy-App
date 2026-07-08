from __future__ import annotations

import logging
import re
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from collegefootballfantasy_api.app.core.security import JWTError, verify_access_token
from collegefootballfantasy_api.app.services.operations_metrics import record_request_metric

logger = logging.getLogger("collegefootballfantasy_api.request")
LEAGUE_ID_PATTERNS = (
    re.compile(r"/leagues/(?P<league_id>\d+)"),
    re.compile(r"/admin/scoring/leagues/(?P<league_id>\d+)"),
)


def _request_id(request: Request) -> str:
    provided = request.headers.get("X-Request-ID") or request.headers.get("X-Correlation-ID")
    if provided:
        return provided[:120]
    return uuid.uuid4().hex


def _league_id(path: str) -> int | None:
    for pattern in LEAGUE_ID_PATTERNS:
        match = pattern.search(path)
        if match:
            return int(match.group("league_id"))
    return None


def _user_id(request: Request) -> int | None:
    authorization = request.headers.get("Authorization")
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    try:
        payload = verify_access_token(token)
        return int(payload.get("sub"))  # type: ignore[arg-type]
    except (JWTError, TypeError, ValueError):
        return None


class RequestTelemetryMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = _request_id(request)
        request.state.request_id = request_id
        league_id = _league_id(request.url.path)
        user_id = _user_id(request)
        started = time.perf_counter()
        status_code = 500
        error_code: str | None = None
        try:
            response = await call_next(request)
            status_code = response.status_code
            if status_code >= 400:
                error_code = f"http_{status_code}"
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception:
            error_code = "unhandled_exception"
            raise
        finally:
            latency_ms = (time.perf_counter() - started) * 1000
            record_request_metric(
                request_id=request_id,
                method=request.method,
                route=request.url.path,
                status=status_code,
                latency_ms=latency_ms,
                user_id=user_id,
                league_id=league_id,
                error_code=error_code,
            )
            logger.info(
                "request completed",
                extra={
                    "request_id": request_id,
                    "user_id": user_id,
                    "league_id": league_id,
                    "route": request.url.path,
                    "method": request.method,
                    "status": status_code,
                    "latency_ms": round(latency_ms, 2),
                    "error_code": error_code,
                },
            )
