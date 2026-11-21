"""Read-only MCP diagnostics for the Raspberry Pi real estate scraper.

Launch with: python mcp_server.py
Requires: pip install "mcp[cli]" psutil psycopg2-binary python-dotenv

The HTTP listener binds to localhost only. Publish it through an authenticated
HTTPS reverse proxy/tunnel; do not forward its port directly from your router.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import psutil
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / "logs"
load_dotenv(ROOT / ".env")

# Streamable HTTP transport. Only a trusted proxy should expose this service.
mcp = FastMCP("Real Estate Pi Diagnostics", host="127.0.0.1", port=8765)
PROCESS_NAMES = (
    "pyparserealestate.py",
    "pyparsesoldrealestate.py",
    "pyenrich_properties_ai.py",
    "pyrefresh_listing_status.py",
)


@mcp.tool()
def get_system_health() -> dict:
    """Read current Pi CPU, RAM, disk and uptime metrics."""
    disk = psutil.disk_usage(str(ROOT))
    memory = psutil.virtual_memory()
    return {
        "cpu_percent": psutil.cpu_percent(interval=0.2),
        "memory_percent": memory.percent,
        "disk_percent": disk.percent,
        "uptime_seconds": round(__import__("time").time() - psutil.boot_time()),
    }


@mcp.tool()
def get_scraper_status() -> dict:
    """Find the four known Python worker scripts without running shell commands."""
    status = {name: [] for name in PROCESS_NAMES}
    for process in psutil.process_iter(["pid", "cmdline"]):
        try:
            command = process.info["cmdline"] or []
            for name in PROCESS_NAMES:
                if any(Path(part).name == name for part in command):
                    status[name].append(process.info["pid"])
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
    return status


@mcp.tool()
def read_scraper_logs(worker: str, lines: int = 50) -> str:
    """Read the end of a known worker log (never an arbitrary file path)."""
    allowed = {"active", "sold", "ai", "status"}
    if worker not in allowed:
        raise ValueError(f"worker must be one of: {', '.join(sorted(allowed))}")
    lines = max(1, min(lines, 200))
    path = LOG_DIR / f"{worker}.log"
    if not path.is_file():
        return f"No log file found for {worker}."
    # Keep memory bounded for large log files.
    from collections import deque
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        return "".join(deque(stream, maxlen=lines))[-30000:]


@mcp.tool()
def get_database_stats() -> dict:
    """Count properties by listing status with a read-only PostgreSQL session."""
    import psycopg2

    connection = psycopg2.connect(
        dbname=os.environ["dbname"],
        user=os.environ["dbuser"],
        password=os.environ["dbpassword"],
        host=os.environ["dbhost"],
        port=os.environ["dbport"],
        connect_timeout=5,
        options="-c default_transaction_read_only=on",
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT COALESCE(listing_status, 'unknown'), COUNT(*)
                   FROM public.properties GROUP BY listing_status"""
            )
            return dict(cursor.fetchall())
    finally:
        connection.close()


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
