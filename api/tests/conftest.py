from __future__ import annotations

from typing import Generator

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from app.main import app, run_startup_tasks

load_dotenv()


@pytest.fixture(scope="session", autouse=True)
def bootstrap() -> None:
    run_startup_tasks()


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client
