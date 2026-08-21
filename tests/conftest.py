from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from collegefootballfantasy_api.app.db.base import Base
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.core.security import create_access_token
from collegefootballfantasy_api.app.main import app
from collegefootballfantasy_api.app.models import (  # noqa: F401
    cfb_standing_snapshot,
    auth_action_token,
    auth_rate_limit_event,
    beta_access,
    college_team,
    draft,
    draft_pick,
    game,
    injury,
    injury_impact,
    league,
    league_invite,
    league_message,
    league_member,
    league_scoring_migration,
    league_settings,
    lineup_week_snapshot,
    matchup,
    mock_draft,
    mock_draft_pick,
    moderation_event,
    notification,
    player,
    player_season_rank,
    player_season_outlook,
    player_stat,
    player_week_score,
    postseason,
    player_waiver_availability,
    provider_identity,
    provider_game_poll,
    provider_sync_state,
    roster,
    refresh_session,
    scheduled_notification,
    scoring_admin_audit,
    scoring_run,
    team_stats_snapshot,
    transaction,
    team,
    team_week_score,
    trade_offer,
    trade_offer_item,
    trade_review,
    standing,
    user,
    waiver_claim,
    waiver_claim_audit,
    waiver_processing_run,
    waiver_period,
    waiver_priority,
    watchlist,
    weekly_projection,
)
from collegefootballfantasy_api.app.models.user import User

TEST_DATABASE_URL = "sqlite://"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture(autouse=True)
def certified_calendar_for_workflow_tests(monkeypatch: pytest.MonkeyPatch):
    """Inject deterministic certification for workflow tests only.

    Production intentionally has no fabricated 2026 schedule artifact. Tests
    exercising draft completion and postseason lifecycles use this explicit
    in-memory dependency; source-validation tests use the real file path.
    """
    from collegefootballfantasy_api.app.services.season_calendar import CertifiedSeasonCalendar
    import collegefootballfantasy_api.app.services.postseason_service as postseason_service

    rounds_by_size = {2: 1, 4: 2, 6: 3, 8: 3}

    def fixture_calendar(season: int, playoff_team_count: int) -> CertifiedSeasonCalendar:
        rounds = rounds_by_size[playoff_team_count]
        championship_week = 13
        playoff_start_week = championship_week - rounds + 1
        return CertifiedSeasonCalendar(
            season=season,
            playoff_team_count=playoff_team_count,
            regular_season_start_week=1,
            regular_season_end_week=playoff_start_week - 1,
            playoff_start_week=playoff_start_week,
            championship_week=championship_week,
            max_rounds=rounds,
            calendar_policy_version="test-sealed-calendar",
            source_identity="test-fixture",
            source_revision="test-fixture-v1",
            source_sha256="0" * 64,
            source_format_version="test-sealed-schedule-v1",
        )

    monkeypatch.setattr(postseason_service, "calendar_for_season", fixture_calendar)


def override_get_db() -> Generator[Session, None, None]:
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def admin_headers(client: TestClient) -> dict[str, str]:
    """Create one test-only administrator for protected ingestion endpoints."""
    email = "admin-seed@example.com"
    with TestingSessionLocal() as session:
        user = session.query(User).filter(User.email == email).one_or_none()
        if user is not None:
            user_id = user.id

    if user is None:
        response = client.post(
            "/auth/signup",
            json={
                "first_name": "Admin",
                "email": email,
                "password": "StrongPass123!",
            },
        )
        assert response.status_code == 201
        with TestingSessionLocal() as session:
            user = session.query(User).filter(User.email == email).one()
            user.is_admin = True
            session.commit()
            user_id = user.id

    token, _ = create_access_token(user_id=user_id, email=email)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(name="client")
def client_fixture() -> Generator[TestClient, None, None]:
    # Unit/API tests that are not specifically exercising beta access must not
    # inherit the developer machine's beta gate.  Individual beta-access tests
    # opt in with their dedicated fixture, which restores this test default.
    original_beta_access_enabled = settings.beta_access_enabled
    settings.beta_access_enabled = False
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        settings.beta_access_enabled = original_beta_access_enabled


@pytest.fixture(name="db_session")
def db_session_fixture() -> Generator[Session, None, None]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
