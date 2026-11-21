#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
if [[ -x .venv/bin/python ]]; then PYTHON=.venv/bin/python
elif [[ -x venv/bin/python ]]; then PYTHON=venv/bin/python
else PYTHON=python3; fi
exec "$PYTHON" pyrefresh_listing_status.py "$@"
