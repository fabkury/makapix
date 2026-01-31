#!/bin/bash
# Create the API worker user with limited privileges
# This script runs after init.sql during PostgreSQL container initialization

set -e

# Only create API worker user if environment variables are set
if [ -n "$DB_API_WORKER_USER" ] && [ -n "$DB_API_WORKER_PASSWORD" ]; then
    echo "Creating API worker user: $DB_API_WORKER_USER"
    
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
        -- Create the API worker role
        DO \$\$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '$DB_API_WORKER_USER') THEN
                CREATE ROLE "$DB_API_WORKER_USER" WITH LOGIN;
            END IF;
        END
        \$\$;

        -- Always update password (ensures password matches .env even if role existed)
        ALTER ROLE "$DB_API_WORKER_USER" WITH PASSWORD '$DB_API_WORKER_PASSWORD';
        
        -- Grant connect privilege to the database
        GRANT CONNECT ON DATABASE "$POSTGRES_DB" TO "$DB_API_WORKER_USER";
        
        -- Grant usage on public schema
        GRANT USAGE ON SCHEMA public TO "$DB_API_WORKER_USER";
        
        -- Grant SELECT, INSERT, UPDATE, DELETE on all current tables
        GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "$DB_API_WORKER_USER";
        
        -- Grant same privileges on future tables
        ALTER DEFAULT PRIVILEGES IN SCHEMA public 
            GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "$DB_API_WORKER_USER";
        
        -- Grant USAGE and SELECT on all sequences (for auto-increment columns)
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO "$DB_API_WORKER_USER";
        
        -- Grant same privileges on future sequences
        ALTER DEFAULT PRIVILEGES IN SCHEMA public 
            GRANT USAGE, SELECT ON SEQUENCES TO "$DB_API_WORKER_USER";
EOSQL

    echo "API worker user '$DB_API_WORKER_USER' created with read/write privileges"

    # Create test database for automated tests
    echo "Creating test database: makapix_test"

    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "postgres" <<-EOSQL
        -- Create the test database if it doesn't exist
        SELECT 'CREATE DATABASE makapix_test'
        WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'makapix_test')\gexec
EOSQL

    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "makapix_test" <<-EOSQL
        -- Create required extensions
        CREATE EXTENSION IF NOT EXISTS pgcrypto;
        CREATE EXTENSION IF NOT EXISTS pg_trgm;

        -- Grant connect privilege to the test database
        GRANT CONNECT ON DATABASE makapix_test TO "$DB_API_WORKER_USER";

        -- Grant usage and create on public schema
        GRANT USAGE, CREATE ON SCHEMA public TO "$DB_API_WORKER_USER";

        -- Grant SELECT, INSERT, UPDATE, DELETE on all current tables
        GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "$DB_API_WORKER_USER";

        -- Grant same privileges on future tables
        ALTER DEFAULT PRIVILEGES IN SCHEMA public
            GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "$DB_API_WORKER_USER";

        -- Grant USAGE and SELECT on all sequences
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO "$DB_API_WORKER_USER";

        -- Grant same privileges on future sequences
        ALTER DEFAULT PRIVILEGES IN SCHEMA public
            GRANT USAGE, SELECT ON SEQUENCES TO "$DB_API_WORKER_USER";
EOSQL

    echo "Test database 'makapix_test' created with privileges for '$DB_API_WORKER_USER'"
else
    echo "DB_API_WORKER_USER or DB_API_WORKER_PASSWORD not set, skipping API worker user creation"
fi

