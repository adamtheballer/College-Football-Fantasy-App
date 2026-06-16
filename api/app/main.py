import logging
from contextlib import asynccontextmanager
from time import perf_counter
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from api.app.api.routes import (
    automation,
    auth,
    health,
    insights,
    injuries,
    league_game,
    leagues,
    matchups,
    mock_drafts,
    news,
    notifications,
    ops,
    players,
    projections,
    rosters,
    schedule,
    stats,
    teams,
    trades,
    waivers,
    watchlists,
)
from api.app.core.config import settings
from api.app.core.logging import configure_logging
from api.app.models import load_model_registry
from api.app.services.draft_timeout_runner import draft_timeout_runner
from api.app.services.realtime_relay import draft_realtime_relay

load_model_registry()
configure_logging(settings.api_log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def app_lifespan(_app: FastAPI):
    await draft_realtime_relay.start()
    await draft_timeout_runner.start()
    try:
        yield
    finally:
        await draft_timeout_runner.stop()
        await draft_realtime_relay.stop()


app = FastAPI(title="CollegeFootballFantasy API", lifespan=app_lifespan)


def _extract_origin(url: str) -> str | None:
    value = (url or "").strip()
    if not value:
        return None
    parsed = urlparse(value if "://" in value else f"https://{value}")
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def build_cors_origins() -> list[str]:
    origins = list(settings.cors_origin_list)
    for configured_url in (settings.ui_base_url, settings.public_web_url):
        origin = _extract_origin(configured_url)
        if origin:
            origins.append(origin)
    return list(dict.fromkeys(origins))


app.add_middleware(
    CORSMiddleware,
    allow_origins=build_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid4().hex
    started = perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (perf_counter() - started) * 1000.0
        logger.exception(
            "http_request_failed request_id=%s method=%s path=%s duration_ms=%.2f",
            request_id,
            request.method,
            request.url.path,
            duration_ms,
        )
        raise
    duration_ms = (perf_counter() - started) * 1000.0
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "http_request request_id=%s method=%s path=%s status=%s duration_ms=%.2f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


app.include_router(health.router)
app.include_router(ops.router)
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(leagues.router, prefix="/leagues", tags=["leagues"])
app.include_router(league_game.router, tags=["league-game"])
app.include_router(mock_drafts.router, prefix="/mock-drafts", tags=["mock-drafts"])
app.include_router(news.router, prefix="/news", tags=["news"])
app.include_router(teams.router, tags=["teams"])
app.include_router(players.router, prefix="/players", tags=["players"])
app.include_router(rosters.router, tags=["rosters"])
app.include_router(projections.router, prefix="/projections", tags=["projections"])
app.include_router(injuries.router, prefix="/injuries", tags=["injuries"])
app.include_router(matchups.router, prefix="/matchups", tags=["matchups"])
app.include_router(schedule.router, prefix="/schedule", tags=["schedule"])
app.include_router(stats.router, prefix="/stats", tags=["stats"])
app.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
app.include_router(watchlists.router, prefix="/watchlists", tags=["watchlists"])
app.include_router(trades.router, prefix="/trades", tags=["trades"])
app.include_router(waivers.router, tags=["waivers"])
app.include_router(insights.router, prefix="/insights", tags=["insights"])
app.include_router(automation.router, tags=["automation"])
