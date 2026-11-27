# Mac local-AI environment

This setup runs the AI model on the Mac while PostgreSQL and the scrapers remain on the Raspberry Pi.

## Database details

The pgAdmin connection supplies these values:

- Database: `propertydb`
- PostgreSQL user: `postgres`
- PostgreSQL address on the Pi: `127.0.0.1:5432`

pgAdmin's SSH tunnel is internal to pgAdmin. The Python process therefore uses its own SSH tunnel, exposed on the Mac as `127.0.0.1:5433`.

## Setup

From the repository root:

```bash
cd mac_environment
cp .env.example .env
chmod +x start_db_tunnel.sh
```

Open `.env` and enter the PostgreSQL password after `PGPASSWORD=`. Do not commit `.env`.

Install and start Ollama:

```bash
brew install ollama
brew services start ollama
ollama pull qwen3.5:4b
```

## Connect to the Pi database

In one terminal:

```bash
cd mac_environment
./start_db_tunnel.sh
```

Leave that terminal open. In a second terminal, activate the project's Python environment and run the enrichment process.

If `raspberrypi.local` does not resolve, replace it in `start_db_tunnel.sh` with the Pi's LAN IP address.

## Test the tunnel

If PostgreSQL's command-line client is installed:

```bash
PGPASSWORD='your-password' psql \
  -h 127.0.0.1 \
  -p 5433 \
  -U postgres \
  -d propertydb \
  -c 'SELECT current_database(), current_user;'
```

The local port is deliberately `5433` so it does not collide with PostgreSQL already running on the Mac.
