#!/usr/bin/env bash
# PROPERTY PIPELINE
# -----------------
# Run four independent jobs forever:
#   1. active  -> discover currently advertised properties
#   2. sold    -> discover sold properties
#   3. ai      -> enrich stored descriptions with AI
#   4. status  -> revisit unsold properties for sale updates
#
# Each job waits six hours AFTER it finishes before running again.
# Logs are written to logs/<job>.log.
# Stop the pipeline with Ctrl+C.

set -Eeuo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

SLEEP_SECONDS="${INTERVAL_SECONDS:-21600}" # 6 hours
LOG_DIR="$PROJECT_DIR/logs"

if ! [[ "$SLEEP_SECONDS" =~ ^[0-9]+$ ]] || (( SLEEP_SECONDS < 1 )); then
  echo "INTERVAL_SECONDS must be a positive number of seconds." >&2
  exit 2
fi

mkdir -p "$LOG_DIR"

# Keep a PID for each background job so they can be stopped together.
PIDS=()

stop_all() {
  trap - INT TERM EXIT
  echo
  echo "Stopping property pipeline..."
  for pid in "${PIDS[@]}"; do
    # Kill the entire process group if supported; otherwise kill the worker.
    pkill -TERM -P "$pid" 2>/dev/null || true
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap stop_all INT TERM EXIT

# One worker is one endless loop. An error is logged, not fatal to other jobs.
run_forever() {
  local name="$1"
  local launcher="$2"

  while true; do
    echo "[$(date -Is)] $name: started"
    if bash "$PROJECT_DIR/$launcher" >> "$LOG_DIR/$name.log" 2>&1; then
      echo "[$(date -Is)] $name: completed"
    else
      echo "[$(date -Is)] $name: failed (check logs/$name.log)"
    fi

    echo "[$(date -Is)] $name: sleeping $SLEEP_SECONDS seconds"
    sleep "$SLEEP_SECONDS"
  done
}

# Start jobs in parallel. Their sleep timers are independent.
run_forever "active" "run_active.sh" & PIDS+=("$!")
run_forever "sold" "run_sold.sh" & PIDS+=("$!")
run_forever "ai" "run_ai_enrichment.sh" & PIDS+=("$!")
run_forever "status" "run_status_refresh.sh" & PIDS+=("$!")

echo "Property pipeline started: 4 jobs, each with a 6-hour cooldown."
echo "Logs: $LOG_DIR"
echo "Press Ctrl+C to stop."
wait
