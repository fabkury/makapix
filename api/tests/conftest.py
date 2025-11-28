from __future__ import annotations

from typing import Generator

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.main import app, run_startup_tasks

load_dotenv()


@pytest.fixture(scope="session", autouse=True)
def bootstrap() -> None:
    run_startup_tasks()


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    """Create a database session for testing."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
