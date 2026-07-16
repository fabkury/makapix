"""
Test configuration with separate test database.

Uses pytest_configure hook to set TEST_DATABASE_URL before any app modules
are imported during test collection.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Generator
from urllib.parse import quote_plus

import pytest

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from fastapi.testclient import TestClient


def pytest_configure(config):
    """Set TEST_DATABASE_URL before any test modules are imported."""
    api_user = os.getenv("DB_API_WORKER_USER")
    api_pass = os.getenv("DB_API_WORKER_PASSWORD")
    db_host = os.getenv("DB_HOST", "db")
    db_port = os.getenv("DB_PORT", "5432")

    if api_user and api_pass:
        encoded_pass = quote_plus(api_pass)
        os.environ["TEST_DATABASE_URL"] = (
            f"postgresql+psycopg://{api_user}:{encoded_pass}@{db_host}:{db_port}/makapix_test"
        )


def get_test_admin_url() -> str:
    """Get admin URL for running migrations on test database."""
    admin_user = os.getenv("DB_ADMIN_USER")
    admin_pass = os.getenv("DB_ADMIN_PASSWORD")
    db_host = os.getenv("DB_HOST", "db")
    db_port = os.getenv("DB_PORT", "5432")

    if admin_user and admin_pass:
        encoded_pass = quote_plus(admin_pass)
        return f"postgresql+psycopg://{admin_user}:{encoded_pass}@{db_host}:{db_port}/makapix_test"

    raise RuntimeError("DB_ADMIN_USER and DB_ADMIN_PASSWORD must be set for migrations")


# Lazy initialization of test engine and session factory
_test_engine = None
_TestSessionLocal = None


def _get_test_engine():
    global _test_engine
    if _test_engine is None:
        from sqlalchemy import create_engine

        _test_engine = create_engine(
            os.environ["TEST_DATABASE_URL"],
            pool_pre_ping=True,
        )
    return _test_engine


def _get_test_session_local():
    global _TestSessionLocal
    if _TestSessionLocal is None:
        from sqlalchemy.orm import sessionmaker

        _TestSessionLocal = sessionmaker(
            bind=_get_test_engine(), autoflush=False, autocommit=False
        )
    return _TestSessionLocal


@pytest.fixture(scope="session", autouse=True)
def setup_test_database() -> Generator[None, None, None]:
    """Create test database schema at session start."""
    from sqlalchemy import create_engine, text
    from app.db import Base
    import app.models  # noqa: F401 - Import models to register them with Base.metadata

    # Create admin engine for DDL operations
    admin_engine = create_engine(get_test_admin_url(), pool_pre_ping=True)

    # Drop and recreate the public schema to ensure clean state
    api_worker = os.getenv("DB_API_WORKER_USER", "api_worker")
    with admin_engine.connect() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.execute(text(f'GRANT USAGE ON SCHEMA public TO "{api_worker}"'))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        conn.commit()

    # Create tables from models
    with admin_engine.begin() as conn:
        Base.metadata.create_all(conn)
        # `handle_sequence` backs generate_default_handle() but is a raw migration
        # artifact, not a model-declared Sequence, so create_all() skips it. Mirror
        # the squashed migration so registration-path tests work. Created before the
        # ALL SEQUENCES grant below so api_worker gets USAGE on it.
        conn.execute(text("CREATE SEQUENCE IF NOT EXISTS handle_sequence START WITH 1"))

    # Grant permissions to api_worker on all tables and sequences
    with admin_engine.begin() as conn:
        conn.execute(
            text(
                f'GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA public TO "{api_worker}"'
            )
        )
        conn.execute(
            text(
                f'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO "{api_worker}"'
            )
        )

    admin_engine.dispose()

    # Dispose the app engine pool to clear any stale connections
    from app.db import engine as app_engine

    app_engine.dispose()

    # Run seed data
    from app.seed import ensure_seed_data

    ensure_seed_data()

    yield


@pytest.fixture()
def db() -> Generator["Session", None, None]:
    """Provide a database session that truncates tables after each test."""
    from sqlalchemy import text
    from app.db import Base

    SessionLocal = _get_test_session_local()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()

        # Truncate all tables for test isolation using CASCADE
        table_names = [f'"{table.name}"' for table in Base.metadata.sorted_tables]
        if table_names:
            truncate_sql = f"TRUNCATE TABLE {', '.join(table_names)} CASCADE"
            session.execute(text(truncate_sql))
            session.commit()
        session.close()


@pytest.fixture()
def client(db: "Session") -> Generator["TestClient", None, None]:
    """Provide a test client with database dependency overridden."""
    from fastapi.testclient import TestClient
    from app.db import get_session
    from app.main import app

    def _get_test_session():
        SessionLocal = _get_test_session_local()
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    # Override the get_session dependency to use test database
    app.dependency_overrides[get_session] = _get_test_session

    with TestClient(app) as test_client:
        yield test_client

    # Clean up override
    app.dependency_overrides.pop(get_session, None)


@pytest.fixture(autouse=True)
def _no_live_celery(monkeypatch) -> None:
    """Stop tests from enqueuing real Celery tasks.

    An endpoint's fire-and-forget `task.delay(...)` would otherwise hit the
    shared broker and be executed by the LIVE worker against the LIVE database
    (small-int test ids collide with real rows). Neutralise .delay/.apply_async;
    tests that need a task to run call .apply() explicitly, which is eager and
    unaffected.
    """
    from celery.app.task import Task

    class _NoopResult:
        id = "test-noop"

        def get(self, *a, **k):
            return None

    monkeypatch.setattr(Task, "delay", lambda self, *a, **k: _NoopResult())
    monkeypatch.setattr(Task, "apply_async", lambda self, *a, **k: _NoopResult())


@pytest.fixture(autouse=True)
def _reset_rate_limits() -> Generator[None, None, None]:
    """Flush rate-limit counters before each test.

    Rate limits live in the shared dev Redis, which is not reset between test
    runs; without this, throttle counters accumulate across tests/reruns and
    cause spurious 429s. Flushing only at test start preserves within-test
    accumulation (so 429-asserting tests still work).
    """
    try:
        from app.services.rate_limit import get_redis_client

        r = get_redis_client()
        if r:
            keys = list(r.scan_iter("ratelimit:*"))
            if keys:
                r.delete(*keys)
    except Exception:
        pass
    yield
