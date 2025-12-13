#!/usr/bin/env bash
# Start green + white agents locally for testing (HTTP on localhost).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

LOG_DIR=${LOG_DIR:-logs/local}
mkdir -p "$LOG_DIR"

GREEN_PORT=${GREEN_PORT:-9101}
WHITE_PORT=${WHITE_PORT:-9102}

echo "Starting green agent on http://localhost:${GREEN_PORT} ..."
AGENT_HOST=127.0.0.1 AGENT_PORT=${GREEN_PORT} PUBLIC_URL="http://localhost:${GREEN_PORT}" \
  python main.py green > "${LOG_DIR}/green.log" 2>&1 &
GREEN_PID=$!

echo "Starting white agent on http://localhost:${WHITE_PORT} ..."
AGENT_HOST=127.0.0.1 AGENT_PORT=${WHITE_PORT} PUBLIC_URL="http://localhost:${WHITE_PORT}" \
  python main.py white > "${LOG_DIR}/white.log" 2>&1 &
WHITE_PID=$!

echo "Green PID: ${GREEN_PID}, log: ${LOG_DIR}/green.log"
echo "White PID: ${WHITE_PID}, log: ${LOG_DIR}/white.log"
echo "To stop: kill ${GREEN_PID} ${WHITE_PID}"
