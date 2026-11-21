#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ ! -f ".venv/bin/activate" ]]; then
    echo "Missing virtual environment: $SCRIPT_DIR/.venv" >&2
    echo "Create it first, then install requirements.txt." >&2
    exit 1
fi

# shellcheck disable=SC1091
source ".venv/bin/activate"

mode="${1:-all}"

case "$mode" in
    active)
        python pyparserealestate.py
        ;;
    sold)
        python pyparsesoldrealestate.py
        ;;
    all)
        python pyparserealestate.py
        python pyparsesoldrealestate.py
        ;;
    *)
        echo "Usage: $0 [active|sold|all]" >&2
        exit 2
        ;;
esac
