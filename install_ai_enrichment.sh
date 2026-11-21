#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install python-dotenv psycopg2-binary
if [[ ! -f .env ]]; then
  printf '%s\n' 'Create a .env file with your existing dbuser, dbpassword, dbhost, dbport, dbname and OPENAI_API_KEY.' 
fi
echo "Apply sql/add_ai_prediction_fields.sql to PostgreSQL before running the AI enrichment."
echo "Then run: bash run_ai_enrichment.sh --dry-run --limit 5"
