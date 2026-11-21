#!/usr/bin/env bash
#
# Export the PostgreSQL database schema to sql/.
#
# Usage:
#   bash export_db_schema.sh
#
# This exports STRUCTURE ONLY (no property data).
# Requires: pg_dump, python3, and the project's .env file.
#
set -Eeuo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Read database settings from the same .env keys used by pyDB.py.
# Use Python rather than sourcing .env as shell code (which would execute it).
read_db_config() {
  python3 - <<'PY'
from pathlib import Path
import os
import shlex

config = {}
env_path = Path(".env")
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        config[key] = value
for env_key, config_key in (
    ("PGHOST", "dbhost"),
    ("PGPORT", "dbport"),
    ("PGUSER", "dbuser"),
    ("PGDATABASE", "dbname"),
    ("PGPASSWORD", "dbpassword"),
):
    value = os.environ.get(env_key) or os.environ.get(config_key) or config.get(config_key, "")
    if value:
        print(f"export {env_key}={shlex.quote(value)}")
PY
}

if ! command -v pg_dump >/dev/null 2>&1; then
  echo "Error: pg_dump is not installed. Install postgresql-client." >&2
  exit 1
fi

# eval is safe here: read_db_config emits only shell-quoted 'export' statements
# from the Python shlex.quote function, not raw .env contents.
eval "$(read_db_config)"

: "${PGDATABASE:?Missing dbname in .env (or PGDATABASE)}"
: "${PGUSER:?Missing dbuser in .env (or PGUSER)}"
export PGHOST="${PGHOST:-localhost}"
export PGPORT="${PGPORT:-5432}"

OUTPUT_DIR="$PROJECT_DIR/sql"
mkdir -p "$OUTPUT_DIR"

# Fixed output names make repeated exports easy to review in Git.
# Write to a temporary file first, so a failed dump never destroys an old export.
TEMP_FILE="$(mktemp "$OUTPUT_DIR/.schema.XXXXXXXX.sql")"
trap 'rm -f "$TEMP_FILE"' EXIT

echo "Exporting database schema from ${PGHOST}:${PGPORT}/${PGDATABASE}..."
pg_dump \
  --schema-only \
  --no-owner \
  --no-privileges \
  --no-comments \
  --file="$TEMP_FILE"

mv "$TEMP_FILE" "$OUTPUT_DIR/database_schema.sql"
trap - EXIT

echo "Done: sql/database_schema.sql"
echo "Includes tables, functions, procedures, views, triggers, indexes and constraints."
echo "No table data was exported. Review the file before committing."
