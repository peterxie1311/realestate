# PostgreSQL-only MCP server on Raspberry Pi

The MCP server can inspect all schemas and tables that its PostgreSQL login
can read. It has no operating-system or scraper-control tools.

## Install

```bash
cd ~/realestate
git switch codex
git pull origin codex
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-mcp.txt
python mcp_server.py
```

Local MCP endpoint: `http://127.0.0.1:8765/mcp`.

## Database permissions (important)

Create a dedicated login as a PostgreSQL administrator, using a strong unique
password. For each database schema you want accessible, grant USAGE on the
schema and SELECT on its tables. Example for the public schema:

```sql
CREATE ROLE mcp_reader LOGIN PASSWORD 'REPLACE_WITH_LONG_RANDOM_PASSWORD';
GRANT CONNECT ON DATABASE your_database TO mcp_reader;
GRANT USAGE ON SCHEMA public TO mcp_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO mcp_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO mcp_reader;
```

Repeat the schema grants for any other schemas you want available. Default
privileges only apply to future tables created by the role whose defaults are
altered; repeat for other table-owner roles if needed. Do not give this login
superuser, CREATE, or write privileges.

Add these variables to the Pi's local `.env` (never commit this file):

```dotenv
MCP_DB_USER=mcp_reader
MCP_DB_PASSWORD=REPLACE_WITH_LONG_RANDOM_PASSWORD
```

The server retains existing `dbhost`, `dbport`, and `dbname` variables.
The database enforces read-only transactions and a 10-second statement timeout.
Queries return at most 500 rows per request. Query results may contain sensitive
data; grant access only to the tables you intend to expose to ChatGPT.

## No port forwarding

The MCP listener binds to `127.0.0.1:8765` and is not internet-accessible.

For a **cloud-hosted ChatGPT MCP connector**, use an authenticated HTTPS
gateway/tunnel (for example, Cloudflare Tunnel with an appropriate OAuth
gateway) that supports streamable HTTP MCP and verifies authorization on every
request. Do not expose the unauthenticated local MCP endpoint directly through
a public tunnel, Tailscale Funnel or router port forwarding.

Tailscale by itself only provides private connectivity between tailnet devices;
it does not automatically let cloud-hosted ChatGPT reach the Pi.

## Available tools

- `list_schemas()`
- `list_tables(schema=None)`
- `describe_table(schema, table)`
- `query_database(sql_query, max_rows=100)`

The remote connector is **not configured** by committing this code. You must
run the service on the Pi and connect an authenticated endpoint in ChatGPT.
