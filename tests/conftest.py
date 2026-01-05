import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from api.app.db.base import Base
from api.app.db.session import get_db
from api.app.main import app
from api.app.models import league, player, roster, team  # noqa: F401

TEST_DATABASE_URL = "sqlite:///./test.db"


def override_get_db() -> Generator[Session, None, None]:
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(name="client")
def client_fixture() -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    if os.path.exists("./test.db"):
        os.remove("./test.db")
