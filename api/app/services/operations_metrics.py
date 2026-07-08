from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any


MAX_RECENT_REQUESTS = 100


@dataclass
class OperationsMetrics:
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    request_count: int = 0
    total_latency_ms: float = 0.0
    status_counts: Counter[str] = field(default_factory=Counter)
    route_counts: Counter[str] = field(default_factory=Counter)
    error_counts: Counter[str] = field(default_factory=Counter)
    auth_failures: int = 0
    draft_pick_latency_ms: list[float] = field(default_factory=list)
    provider_sync_latency_ms: list[float] = field(default_factory=list)
    scoring_run_latency_ms: list[float] = field(default_factory=list)
    waiver_processing_latency_ms: list[float] = field(default_factory=list)
    trade_processing_failures: int = 0
    recent_requests: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=MAX_RECENT_REQUESTS))


_metrics = OperationsMetrics()
_lock = Lock()


def _average(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def record_request_metric(
    *,
    request_id: str,
    method: str,
    route: str,
    status: int,
    latency_ms: float,
    user_id: int | None = None,
    league_id: int | None = None,
    error_code: str | None = None,
) -> None:
    status_group = f"{status // 100}xx"
    with _lock:
        _metrics.request_count += 1
        _metrics.total_latency_ms += latency_ms
        _metrics.status_counts[status_group] += 1
        _metrics.route_counts[f"{method} {route}"] += 1
        if error_code:
            _metrics.error_counts[error_code] += 1
        if route.startswith("/auth") and status in {401, 403, 429}:
            _metrics.auth_failures += 1
        if "/draft" in route and method == "POST":
            _metrics.draft_pick_latency_ms.append(latency_ms)
        if route.startswith("/admin/provider-sync") and method == "POST":
            _metrics.provider_sync_latency_ms.append(latency_ms)
        if route.startswith("/admin/scoring") and method in {"POST", "PUT", "PATCH"}:
            _metrics.scoring_run_latency_ms.append(latency_ms)
        if "/waivers" in route and method == "POST":
            _metrics.waiver_processing_latency_ms.append(latency_ms)
        if "/trades" in route and status >= 500:
            _metrics.trade_processing_failures += 1
        _metrics.recent_requests.appendleft(
            {
                "request_id": request_id,
                "method": method,
                "route": route,
                "status": status,
                "latency_ms": round(latency_ms, 2),
                "user_id": user_id,
                "league_id": league_id,
                "error_code": error_code,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )


def operations_metrics_snapshot() -> dict[str, Any]:
    with _lock:
        request_count = _metrics.request_count
        average_latency = round(_metrics.total_latency_ms / request_count, 2) if request_count else 0.0
        return {
            "started_at": _metrics.started_at,
            "request_count": request_count,
            "average_latency_ms": average_latency,
            "status_counts": dict(_metrics.status_counts),
            "route_counts": dict(_metrics.route_counts.most_common(25)),
            "error_counts": dict(_metrics.error_counts),
            "auth_failures": _metrics.auth_failures,
            "draft_pick_average_latency_ms": _average(_metrics.draft_pick_latency_ms),
            "provider_sync_average_latency_ms": _average(_metrics.provider_sync_latency_ms),
            "scoring_run_average_latency_ms": _average(_metrics.scoring_run_latency_ms),
            "waiver_processing_average_latency_ms": _average(_metrics.waiver_processing_latency_ms),
            "trade_processing_failures": _metrics.trade_processing_failures,
            "recent_requests": list(_metrics.recent_requests),
        }
