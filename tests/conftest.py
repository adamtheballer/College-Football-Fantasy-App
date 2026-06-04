from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.app.db.base import Base
from api.app.db.session import get_db
from api.app.main import app
from api.app.core.config import settings
from api.app.models import (  # noqa: F401
    admin_action,
    cfb_standing_snapshot,
    draft,
    draft_pick,
    draft_team_queue_item,
    draft_timer_state,
    domain_event,
    mock_draft_event,
    mock_draft_lobby_member,
    mock_draft_participant,
    mock_draft_pick,
    mock_draft_queue_item,
    mock_draft_roster,
    mock_draft_seat,
    mock_draft_session,
    mock_draft_timer_state,
    game,
    injury,
    injury_impact,
    idempotency_request,
    league,
    league_invite,
    league_member,
    league_week_state,
    lineup,
    fantasy_player_score,
    team_weekly_score,
    league_settings,
    scheduled_league_job,
    notification,
    player,
    player_news_snapshot,
    player_stat,
    provider_sync_state,
    roster,
    scoring_run,
    refresh_session,
    scheduled_notification,
    team_stats_snapshot,
    trade_offer,
    trade_offer_item,
    waiver_claim,
    transaction,
    team,
    user,
    watchlist,
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
    prior_timeout_runner_enabled = settings.draft_timeout_runner_enabled
    settings.draft_timeout_runner_enabled = False
    with TestClient(app) as client:
        yield client
    settings.draft_timeout_runner_enabled = prior_timeout_runner_enabled
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(name="db_session")
def db_session_fixture() -> Generator[Session, None, None]:
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
