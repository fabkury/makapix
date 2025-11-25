from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from app.db import Base

config = context.config

if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_admin_url() -> str:
    """Get the admin database URL for migrations (requires DDL privileges)."""
    # First try explicit URL
    url = config.get_main_option("sqlalchemy.url") or os.getenv("DB_ADMIN_URL")
    if url:
        return url
    
    # Otherwise construct from components
    admin_user = os.getenv("DB_ADMIN_USER")
    admin_pass = os.getenv("DB_ADMIN_PASSWORD")
    db_name = os.getenv("DB_DATABASE")
    db_host = os.getenv("DB_HOST", "db")
    db_port = os.getenv("DB_PORT", "5432")
    
    if admin_user and admin_pass and db_name:
        # URL-encode the password in case it contains special characters
        from urllib.parse import quote_plus
        encoded_pass = quote_plus(admin_pass)
        return f"postgresql+psycopg://{admin_user}:{encoded_pass}@{db_host}:{db_port}/{db_name}"
    
    raise RuntimeError(
        "DB_ADMIN_URL must be set, or DB_ADMIN_USER, DB_ADMIN_PASSWORD, and DB_DATABASE must all be set."
    )


def run_migrations_offline() -> None:
    url = get_admin_url()

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Migrations require admin privileges for DDL operations (CREATE, DROP, ALTER)
    url = get_admin_url()
    connectable = create_engine(url, pool_pre_ping=True)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
