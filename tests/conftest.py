from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from collegefootballfantasy_api.app.db.base import Base
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.main import app
from collegefootballfantasy_api.app.models import (  # noqa: F401
    cfb_standing_snapshot,
    auth_action_token,
    auth_rate_limit_event,
    draft,
    draft_pick,
    game,
    injury,
    injury_impact,
    league,
    league_invite,
    league_member,
    league_settings,
    lineup_week_snapshot,
    matchup,
    mock_draft,
    mock_draft_pick,
    notification,
    player,
    player_stat,
    player_week_score,
    provider_player_identity_audit,
    provider_sync_state,
    provider_unmatched_player_row,
    roster,
    refresh_session,
    scheduled_notification,
    scoring_correction_audit,
    scoring_job_lock,
    scoring_run,
    team_stats_snapshot,
    transaction,
    team,
    team_week_score,
    standing,
    user,
    watchlist,
    weekly_projection,
)

TEST_DATABASE_URL = "sqlite://"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def override_get_db() -> Generator[Session, None, None]:
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(name="client")
def client_fixture() -> Generator[TestClient, None, None]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(name="db_session")
def db_session_fixture() -> Generator[Session, None, None]:
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
