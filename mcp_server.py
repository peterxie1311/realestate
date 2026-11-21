"""Read-only PostgreSQL MCP server for Raspberry Pi.

This server offers schema discovery and SELECT queries across all tables the
configured database role can read. It does not expose OS or scraper commands.

Start: python mcp_server.py
Local endpoint: http://127.0.0.1:8765/mcp
"""
from __future__ import annotations

import os
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

mcp = FastMCP("PostgreSQL Read-Only Explorer", host="127.0.0.1", port=8765)
MAX_ROWS = 500
QUERY_TIMEOUT_MS = 10_000


@contextmanager
def _read_only_connection():
    """Use a read-only transaction with a statement timeout for each request.

    The database user should ALSO have only SELECT privileges. PostgreSQL role
    permissions, not SQL string filtering, are the security boundary.
    """
    conn = psycopg2.connect(
        host=os.environ["dbhost"],
        port=os.environ["dbport"],
        dbname=os.environ["dbname"],
        user=os.environ.get("MCP_DB_USER", os.environ["dbuser"]),
        password=os.environ.get("MCP_DB_PASSWORD", os.environ["dbpassword"]),
        connect_timeout=5,
        options=f"-c default_transaction_read_only=on -c statement_timeout={QUERY_TIMEOUT_MS}",
    )
    try:
        conn.set_session(readonly=True, autocommit=False)
        yield conn
    finally:
        conn.rollback()
        conn.close()


def _fetch(query: str, parameters: tuple = (), limit: int = MAX_ROWS) -> list[dict]:
    with _read_only_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, parameters)
            if cursor.description is None:
                raise ValueError("The query must return rows.")
            return [dict(row) for row in cursor.fetchmany(limit)]


@mcp.tool()
def list_schemas() -> list[str]:
    """List accessible non-system PostgreSQL schemas."""
    rows = _fetch(
        """SELECT schema_name FROM information_schema.schemata
           WHERE schema_name <> 'information_schema'
             AND schema_name NOT LIKE 'pg_%'
           ORDER BY schema_name"""
    )
    return [row["schema_name"] for row in rows]


@mcp.tool()
def list_tables(schema: str | None = None) -> list[dict]:
    """List tables and views in all accessible schemas, or one schema."""
    return _fetch(
        """SELECT table_schema, table_name, table_type
           FROM information_schema.tables
           WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
             AND (%s IS NULL OR table_schema = %s)
           ORDER BY table_schema, table_name""",
        (schema, schema),
    )


@mcp.tool()
def describe_table(schema: str, table: str) -> dict:
    """Describe columns, types, nullability, primary keys and foreign keys."""
    columns = _fetch(
        """SELECT column_name, data_type, udt_name, is_nullable,
                  column_default, ordinal_position
           FROM information_schema.columns
           WHERE table_schema = %s AND table_name = %s
           ORDER BY ordinal_position""",
        (schema, table),
    )
    constraints = _fetch(
        """SELECT tc.constraint_name, tc.constraint_type,
                  kcu.column_name, ccu.table_schema AS foreign_schema,
                  ccu.table_name AS foreign_table,
                  ccu.column_name AS foreign_column
           FROM information_schema.table_constraints tc
           LEFT JOIN information_schema.key_column_usage kcu
             ON tc.constraint_catalog = kcu.constraint_catalog
            AND tc.constraint_schema = kcu.constraint_schema
            AND tc.constraint_name = kcu.constraint_name
            AND tc.table_name = kcu.table_name
           LEFT JOIN information_schema.constraint_column_usage ccu
             ON tc.constraint_catalog = ccu.constraint_catalog
            AND tc.constraint_schema = ccu.constraint_schema
            AND tc.constraint_name = ccu.constraint_name
           WHERE tc.table_schema = %s AND tc.table_name = %s
           ORDER BY tc.constraint_name, kcu.ordinal_position""",
        (schema, table),
    )
    return {"schema": schema, "table": table, "columns": columns, "constraints": constraints}


@mcp.tool()
def query_database(sql_query: str, max_rows: int = 100) -> dict:
    """Execute a read-only SQL query, returning at most 500 rows.

    PostgreSQL enforces a read-only transaction and statement timeout.
    A dedicated SELECT-only database role is strongly recommended.
    """
    if not sql_query.strip():
        raise ValueError("SQL query cannot be empty.")
    max_rows = max(1, min(int(max_rows), MAX_ROWS))
    rows = _fetch(sql_query, limit=max_rows + 1)
    return {
        "rows": rows[:max_rows],
        "returned_rows": min(len(rows), max_rows),
        "truncated": len(rows) > max_rows,
        "max_rows": max_rows,
    }


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
