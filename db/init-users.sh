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
                CREATE ROLE "$DB_API_WORKER_USER" WITH LOGIN PASSWORD '$DB_API_WORKER_PASSWORD';
            END IF;
        END
        \$\$;
        
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
else
    echo "DB_API_WORKER_USER or DB_API_WORKER_PASSWORD not set, skipping API worker user creation"
fi

