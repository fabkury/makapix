-- Database bootstrap for Makapix
-- This script runs as the admin user during container initialization

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Set timezone
ALTER SYSTEM SET timezone TO 'UTC';
