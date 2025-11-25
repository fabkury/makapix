from __future__ import annotations

import os
from functools import lru_cache
from typing import Generator
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


def get_database_url() -> str:
    """Get the database URL for API operations (uses API worker user)."""
    # Construct from components using API worker credentials
    api_user = os.getenv("DB_API_WORKER_USER")
    api_pass = os.getenv("DB_API_WORKER_PASSWORD")
    db_name = os.getenv("DB_DATABASE")
    db_host = os.getenv("DB_HOST", "db")
    db_port = os.getenv("DB_PORT", "5432")
    
    if api_user and api_pass and db_name:
        # URL-encode the password in case it contains special characters
        encoded_pass = quote_plus(api_pass)
        return f"postgresql+psycopg://{api_user}:{encoded_pass}@{db_host}:{db_port}/{db_name}"
    
    raise RuntimeError(
        "DB_API_WORKER_USER, DB_API_WORKER_PASSWORD, and DB_DATABASE must all be set."
    )


DATABASE_URL = get_database_url()


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""

engine = create_engine(
    DATABASE_URL,
    future=True,
    echo=os.getenv("LOG_LEVEL", "INFO").upper() == "DEBUG",
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@lru_cache(maxsize=1)
def get_engine():
    return engine


def get_session() -> Generator[Session, None, None]:
    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
