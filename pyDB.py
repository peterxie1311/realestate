"""PostgreSQL access for property scrapers.

Public compatibility functions retain their existing names so callers do not
need to change. SQL values use placeholders; dynamic identifiers use psycopg2.sql.
"""
from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager

import pandas as pd
import psycopg2.pool
from dotenv import load_dotenv
from psycopg2 import sql
from psycopg2.extras import Json

load_dotenv()

# Keep numeric result-type constants for existing callers.
result_type_dict = 1
result_type_array = 2
result_type_rows = 3
result_type_jsontocsv = 4
result_type_boolean = 5
result_type_rows_columns = 6
column_name = "columns"
row_name = "rows"

# Lazy initialization avoids opening a database connection during import.
connection_pool = None


def _pool():
    global connection_pool
    if connection_pool is None:
        connection_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=5,
            dbname=os.environ["dbname"],
            user=os.environ["dbuser"],
            password=os.environ["dbpassword"],
            host=os.environ["dbhost"],
            port=os.environ["dbport"],
        )
    return connection_pool


def get_db_connection():
    """Borrow a connection from the shared pool."""
    return _pool().getconn()


def release_db_connection(conn):
    """Return a borrowed connection to the pool."""
    _pool().putconn(conn)


@contextmanager
def _managed_connection(existing=None):
    """Commit on success, roll back on error, release only owned connections."""
    owned = existing is None
    conn = existing if existing is not None else get_db_connection()
    try:
        yield conn
        if owned:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if owned:
            release_db_connection(conn)


def transformResultsnoJson(cursor, rows):
    """Convert cursor tuples to dictionaries using the selected column names."""
    columns = [description[0] for description in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


def transformResultsDict(cursor, rows):
    return transformResultsnoJson(cursor, rows)


def transformResultsArrayNoJson(rows):
    return [row[0] for row in rows]


def getColumns(result):
    return result[column_name]


def getRows(result):
    return result[row_name]


def _format_results(cursor, rows, result_type):
    """Apply one of the existing output formats to query results."""
    if result_type == result_type_dict:
        return transformResultsnoJson(cursor, rows)
    if result_type == result_type_array:
        return transformResultsArrayNoJson(rows)
    if result_type == result_type_rows:
        return rows
    if result_type == result_type_rows_columns:
        return {
            column_name: [description[0] for description in cursor.description],
            row_name: rows,
        }
    if result_type == result_type_jsontocsv:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as output:
            path = output.name
        if len(rows) == 1 and isinstance(rows[0][0], dict):
            frame = pd.DataFrame([rows[0][0]])
        else:
            frame = pd.DataFrame(transformResultsnoJson(cursor, rows))
        frame.to_csv(path, index=False)
        return path
    if result_type == result_type_boolean:
        return True
    raise ValueError(f"Unsupported result type: {result_type}")


def executeQueryAll(query, inparameters=None, result_type=result_type_dict, conn=None):
    """Run a SELECT query, returning its rows in the requested format."""
    with _managed_connection(conn) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, inparameters)
            rows = cursor.fetchall()
            return _format_results(cursor, rows, result_type)


def executeProcedure(query, inparameters=None, result_type=result_type_boolean):
    """Execute an INSERT, UPDATE, DELETE, or a statement returning rows."""
    with _managed_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, inparameters)
            if result_type == result_type_boolean:
                return True
            rows = cursor.fetchall()
            return _format_results(cursor, rows, result_type)


def insert_links(links: list[str]):
    """Save newly discovered listing links, ignoring duplicates."""
    if not links:
        return
    query = """
        INSERT INTO propertylinks (link)
        VALUES (%s)
        ON CONFLICT (link) DO NOTHING
    """
    with _managed_connection() as connection:
        with connection.cursor() as cursor:
            cursor.executemany(query, [(link,) for link in links])


def get_links() -> list[str]:
    """Get discovered links not yet represented in the properties table."""
    return executeQueryAll(
        """SELECT pl.link
           FROM propertylinks AS pl
           WHERE NOT EXISTS (
               SELECT 1 FROM properties AS p WHERE p.listing_url = pl.link
           )""",
        result_type=result_type_array,
    )


def get_propertydata() -> list[dict]:
    """Return all stored properties (used by the offline reparser)."""
    return executeQueryAll("SELECT * FROM properties")


def _json_value(value):
    """Adapt dictionaries and lists for PostgreSQL JSON/JSONB columns."""
    return Json(value) if isinstance(value, (dict, list)) else value


def insert_property(data: dict):
    """Insert a listing, updating existing rows with the same listing URL."""
    if not data or not data.get("listing_url"):
        raise ValueError("Property must contain a listing_url")

    columns = list(data)
    # sql.Identifier quotes column names safely; %s handles values.
    identifiers = [sql.Identifier(name) for name in columns]
    updates = [
        sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(name), sql.Identifier(name))
        for name in columns if name != "listing_url"
    ]
    query = sql.SQL("""
        INSERT INTO properties ({})
        VALUES ({})
        ON CONFLICT (listing_url)
        DO UPDATE SET {}
    """).format(
        sql.SQL(", ").join(identifiers),
        sql.SQL(", ").join([sql.Placeholder()] * len(columns)),
        sql.SQL(", ").join(updates),
    )
    return executeProcedure(query, tuple(_json_value(data[name]) for name in columns))


def update_property(data: dict):
    """Update a property by id (preferred) or listing_id."""
    if data.get("id") is not None:
        key = "id"
    elif data.get("listing_id") is not None:
        key = "listing_id"
    else:
        raise ValueError("Missing id or listing_id")

    changes = {
        name: value for name, value in data.items()
        if name not in ("id", "listing_id")
    }
    if not changes:
        return False

    assignments = [
        sql.SQL("{} = %s").format(sql.Identifier(name)) for name in changes
    ]
    query = sql.SQL("UPDATE properties SET {} WHERE {} = %s").format(
        sql.SQL(", ").join(assignments),
        sql.Identifier(key),
    )
    values = [_json_value(value) for value in changes.values()]
    return executeProcedure(query, tuple(values + [data[key]]))
