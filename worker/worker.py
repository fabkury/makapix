from __future__ import annotations

import os
from sqlalchemy import create_engine, inspect

from app.tasks import celery_app

if __name__ == "__main__":
    # Connect to the database and print table names
    DATABASE_URL = os.getenv(
        "DATABASE_URL", "postgresql+psycopg://appuser:apppassword@db:5432/appdb"
    )
    
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
