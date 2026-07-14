from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from collegefootballfantasy_api.app.api.routes import (
    auth,
    admin_trades,
    admin_scoring,
    health,
    insights,
    injuries,
    leagues,
    matchups,
    notifications,
    players,
    projections,
    provider_identity,
    rosters,
    schedule,
    stats,
    teams,
    trades,
    waivers,
    watchlists,
)
from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.core.logging import configure_logging
from collegefootballfantasy_api.app.core.middleware import request_context_middleware, security_headers_middleware

configure_logging(settings.api_log_level)

app = FastAPI(title="CollegeFootballFantasy API")
app.middleware("http")(request_context_middleware)
app.middleware("http")(security_headers_middleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_cors_origins,
    allow_origin_regex=settings.allowed_cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(admin_scoring.router, prefix="/admin/scoring", tags=["admin-scoring"])
app.include_router(admin_trades.router, prefix="/admin/trades", tags=["admin-trades"])
app.include_router(leagues.router, prefix="/leagues", tags=["leagues"])
app.include_router(teams.router, tags=["teams"])
app.include_router(players.router, prefix="/players", tags=["players"])
app.include_router(rosters.router, tags=["rosters"])
app.include_router(projections.router, prefix="/projections", tags=["projections"])
app.include_router(provider_identity.router, prefix="/provider-identity", tags=["provider-identity"])
app.include_router(injuries.router, prefix="/injuries", tags=["injuries"])
app.include_router(matchups.router, prefix="/matchups", tags=["matchups"])
app.include_router(schedule.router, prefix="/schedule", tags=["schedule"])
app.include_router(stats.router, prefix="/stats", tags=["stats"])
app.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
app.include_router(watchlists.router, prefix="/watchlists", tags=["watchlists"])
app.include_router(waivers.router, tags=["waivers"])
app.include_router(trades.router, prefix="/trade", tags=["trade"])
app.include_router(trades.league_router, tags=["trade"])
app.include_router(insights.router, prefix="/insights", tags=["insights"])
