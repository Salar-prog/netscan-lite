"""Pytest configuration for ns-lite tests."""

import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from netscan_lite.config import settings
from netscan_lite.db import get_session


@pytest.fixture(name="session")
def session_fixture():
    """Create an in-memory SQLite session for testing."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="db_engine")
def db_engine_fixture():
    """Shared in-memory engine for API tests (client + session writes)."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine


@pytest.fixture(name="client")
def client_fixture(db_engine):
    """Create a FastAPI TestClient with in-memory DB."""
    from fastapi.testclient import TestClient

    from netscan_lite.main import create_app

    def override_get_session():
        with Session(db_engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_get_session

    with TestClient(app) as c:
        yield c


@pytest.fixture(name="auth_headers")
def auth_headers_fixture():
    """Return auth headers for API tests (LDAP_ENABLED=false accepts any token)."""
    return {"Authorization": "Bearer test-token"}


_cli_engine = None


@pytest.fixture(autouse=True)
def _isolate_cli_db(monkeypatch):
    """Redirect CLI's engine to an in-memory DB for each test."""
    global _cli_engine
    _cli_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(_cli_engine)
    monkeypatch.setattr("netscan_lite.db.engine", _cli_engine)
    monkeypatch.setattr("netscan_lite.cli.engine", _cli_engine)
    # Enable dev auth for tests (LDAP_ENABLED=false by default)
    monkeypatch.setattr(settings, "DEV_AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "DEBUG", True)


@pytest.fixture(name="cli_session")
def cli_session_fixture():
    """Session that shares the same in-memory DB as the CLI."""
    with Session(_cli_engine) as session:
        yield session
