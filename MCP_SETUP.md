# Raspberry Pi MCP diagnostics

This is a **read-only** Model Context Protocol server for scraper diagnostics.
It does **not** grant arbitrary SSH access or shell execution.

## 1. Install on the Pi

```bash
git switch codex
git pull origin codex
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-mcp.txt
python mcp_server.py
```

The server listens on **127.0.0.1:8765**, with the streamable HTTP MCP
endpoint at **http://127.0.0.1:8765/mcp**. It is not accessible from the
internet by default. Use a systemd service to keep it running later.

## 2. Network access

**No router port forwarding is necessary.** Tailscale is suitable for private
connections between *your* devices, but ChatGPT's cloud-hosted connector cannot
automatically join your private tailnet.

To connect from ChatGPT, use a publicly reachable HTTPS endpoint via a
properly configured reverse proxy/tunnel with **authentication and access
controls**, and configure the corresponding ChatGPT custom MCP connector if
available on your plan. The MCP server here has **no built-in authentication**:
**do not expose it with an unauthenticated public tunnel, Tailscale Funnel,
or router port forwarding**.

An authenticated gateway must support the MCP streamable HTTP protocol and
forward requests to localhost:8765. Verify authorization on every request.
Consider dedicated, read-only PostgreSQL credentials rather than reusing your
scraper's write-capable database user.

## 3. Available tools

- `get_system_health`: CPU, memory, disk and uptime.
- `get_scraper_status`: process IDs for four known worker scripts.
- `read_scraper_logs(worker, lines)`: last 1-200 lines of one known log.
- `get_database_stats`: count properties grouped by listing status.

Logs may contain private information, so only connect through a trusted,
authenticated integration. No credentials should be committed to GitHub.

## 4. Test locally

Start the server in one terminal, then use the MCP Inspector from a separate
terminal, or an MCP-compatible client, to connect to
`http://127.0.0.1:8765/mcp`.

The server cannot be connected to this chat merely by starting it on the Pi.
The external HTTPS gateway and ChatGPT-side connector setup are separate steps.
