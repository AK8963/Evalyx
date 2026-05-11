"""
Shared pytest fixtures for backend tests.
"""
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Use SQLite for tests (no Postgres required in unit tests)
TEST_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./test_traciq.db"
)

os.environ.setdefault("DATABASE_URL", TEST_DATABASE_URL)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("DEBUG", "True")


@pytest.fixture(scope="session")
def engine():
    from database.models import Base
    eng = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)


@pytest.fixture(scope="function")
def db(engine):
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()
    yield session
    session.rollback()
    session.close()


@pytest.fixture(scope="function")
def client(db):
    from backend.main import app
    from backend.database import get_db

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(client):
    """Register a test user and return JWT auth headers."""
    resp = client.post("/api/auth/register", json={
        "email": "testuser@example.com",
        "name": "Test User"
    })
    if resp.status_code == 400:  # already exists
        resp = client.post("/api/auth/login", json={"email": "testuser@example.com"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_project(client, auth_headers):
    """Create a test project and return it."""
    resp = client.post("/api/projects", json={
        "name": "test-project",
        "description": "A test project"
    }, headers=auth_headers)
    if resp.status_code == 400:
        # Already exists — list and return
        projects = client.get("/api/projects", headers=auth_headers).json()
        return next(p for p in projects if p["name"] == "test-project")
    assert resp.status_code == 201
    return resp.json()
