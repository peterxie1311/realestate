#!/usr/bin/env bash
set -euo pipefail

# Opens localhost:5433 on the Mac and forwards it to PostgreSQL on the Pi.
# Keep this terminal open while running the enrichment process.
exec ssh \
  -N \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=60 \
  -o ServerAliveCountMax=3 \
  -L 5433:127.0.0.1:5432 \
  peter@raspberrypi.local
