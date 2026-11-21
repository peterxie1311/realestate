-- Install a dedicated read-only PostgreSQL login for the MCP server.
-- Run with psql as a database administrator, connected to the TARGET database.
--
-- Example:
--   psql -U postgres -d your_database -f sql/install/001_mcp_reader.sql
--
-- Set the login password separately (not in a committed SQL file):
--   psql -U postgres -d your_database -c "\\password mcp_reader"
--
-- This script is idempotent for the role and existing grants.
-- It grants read access to all non-system schemas and their existing tables.
-- Future-table default privileges must be configured per table-owner role.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_reader') THEN
        CREATE ROLE mcp_reader LOGIN;
    END IF;
END
$$;

-- Explicitly prohibit common elevated role attributes.
ALTER ROLE mcp_reader
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;

-- The script must be run while connected to the intended database.
DO $$
BEGIN
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO mcp_reader', current_database());
END
$$;

DO $$
DECLARE
    s record;
BEGIN
    FOR s IN
        SELECT nspname
        FROM pg_namespace
        WHERE nspname <> 'information_schema'
          AND nspname NOT LIKE 'pg_%'
    LOOP
        EXECUTE format('GRANT USAGE ON SCHEMA %I TO mcp_reader', s.nspname);
        EXECUTE format('GRANT SELECT ON ALL TABLES IN SCHEMA %I TO mcp_reader', s.nspname);
    END LOOP;
END
$$;

-- Do NOT grant write privileges or grant this role to other roles.
-- For future tables, run as each role that creates tables:
-- ALTER DEFAULT PRIVILEGES IN SCHEMA public
--     GRANT SELECT ON TABLES TO mcp_reader;
