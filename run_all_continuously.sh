#!/usr/bin/env bash
# Double-click in a Linux file manager configured to execute shell scripts,
# or run: bash run_all_continuously.sh
set -Eeuo pipefail
DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"
INTERVAL_SECONDS="${INTERVAL_SECONDS:-21600}"
if ! [[ "$INTERVAL_SECONDS" =~ ^[0-9]+$ ]] || (( INTERVAL_SECONDS < 1 )); then
  echo "INTERVAL_SECONDS must be a positive integer" >&2
  exit 2
fi
mkdir -p logs
declare -a PIDS=()
cleanup() {
  trap - INT TERM EXIT
  echo "Stopping all workers..."
  for pid in "${PIDS[@]}"; do kill "$pid" 2>/dev/null || true; done
  wait 2>/dev/null || true
}
trap cleanup INT TERM EXIT

worker() {
  local name="$1" script="$2"
  while true; do
    echo "[$(date -Is)] [$name] Starting"
    if bash "$DIR/$script" >> "$DIR/logs/$name.log" 2>&1; then
      echo "[$(date -Is)] [$name] Finished successfully"
    else
      echo "[$(date -Is)] [$name] Failed; see logs/$name.log"
    fi
    echo "[$(date -Is)] [$name] Sleeping ${INTERVAL_SECONDS}s"
    sleep "$INTERVAL_SECONDS"
  done
}
worker active run_active.sh & PIDS+=("$!")
worker sold run_sold.sh & PIDS+=("$!")
worker ai run_ai_enrichment.sh & PIDS+=("$!")
worker status run_status_refresh.sh & PIDS+=("$!")
echo "Four workers running. Logs: $DIR/logs"
echo "Press Ctrl+C to stop. Each worker sleeps 6 hours after its run."
wait
