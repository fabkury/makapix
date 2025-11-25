from __future__ import annotations

import os
from sqlalchemy import create_engine, inspect

from app.tasks import celery_app

def get_database_url() -> str:
    """Get the database URL for API operations (uses API worker user)."""
    from urllib.parse import quote_plus
    
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


if __name__ == "__main__":
    # Connect to the database and print table names
    DATABASE_URL = get_database_url()
    
    print("=" * 60)
    print("Connecting to database...")
    print(f"Database URL: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else DATABASE_URL}")
    print("=" * 60)
    
    try:
        # Create engine and connect
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        inspector = inspect(engine)
        
        # Get all table names
        table_names = inspector.get_table_names()
        
        print(f"\nFound {len(table_names)} table(s) in the database:\n")
        for i, table_name in enumerate(table_names, 1):
            print(f"  {i}. {table_name}")
        
        print("\n" + "=" * 60)
        print("Database connection successful!")
        print("=" * 60 + "\n")
        
    except Exception as e:
        print(f"\n❌ Error connecting to database: {e}\n")
        print("=" * 60 + "\n")
    
    # Start the Celery worker
    celery_app.worker_main(["worker", "--loglevel=info"])
