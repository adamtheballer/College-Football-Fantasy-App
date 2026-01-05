from fastapi import FastAPI

from collegefootballfantasy_api.app.api.routes import health, leagues, players, rosters, teams
from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.core.logging import configure_logging

configure_logging(settings.api_log_level)

app = FastAPI(title="CollegeFootballFantasy API")

app.include_router(health.router)
app.include_router(leagues.router, prefix="/leagues", tags=["leagues"])
app.include_router(teams.router, tags=["teams"])
app.include_router(players.router, prefix="/players", tags=["players"])
app.include_router(rosters.router, tags=["rosters"])
