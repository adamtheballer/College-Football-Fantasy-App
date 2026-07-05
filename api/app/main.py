from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from collegefootballfantasy_api.app.api.routes import (
    auth,
    health,
    insights,
    injuries,
    leagues,
    matchups,
    notifications,
    players,
    projections,
    rosters,
    schedule,
    stats,
    teams,
    trades,
    watchlists,
)
from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.core.logging import configure_logging

configure_logging(settings.api_log_level)

app = FastAPI(title="CollegeFootballFantasy API")

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
app.include_router(leagues.router, prefix="/leagues", tags=["leagues"])
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
app.include_router(trades.router, prefix="/trade", tags=["trade"])
app.include_router(insights.router, prefix="/insights", tags=["insights"])
