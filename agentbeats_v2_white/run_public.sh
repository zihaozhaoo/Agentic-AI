#!/usr/bin/env bash
# Start green + white agents for public/ingress deployment.
# Requires PUBLIC_URLs to be set to reachable HTTPS endpoints (Cloudflare/ingress).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

: "${PUBLIC_URL_GREEN:?set PUBLIC_URL_GREEN to your external green URL (e.g., https://yourdomain/green)}"
: "${PUBLIC_URL_WHITE:?set PUBLIC_URL_WHITE to your external white URL (e.g., https://yourdomain/white)}"

LOG_DIR=${LOG_DIR:-logs/public}
mkdir -p "$LOG_DIR"

GREEN_PORT=${GREEN_PORT:-8010}
WHITE_PORT=${WHITE_PORT:-8011}

echo "Starting green agent on ${PUBLIC_URL_GREEN} (bind 0.0.0.0:${GREEN_PORT}) ..."
AGENT_HOST=0.0.0.0 AGENT_PORT=${GREEN_PORT} PUBLIC_URL="${PUBLIC_URL_GREEN}" \
  python main.py green > "${LOG_DIR}/green.log" 2>&1 &
GREEN_PID=$!

echo "Starting white agent on ${PUBLIC_URL_WHITE} (bind 0.0.0.0:${WHITE_PORT}) ..."
AGENT_HOST=0.0.0.0 AGENT_PORT=${WHITE_PORT} PUBLIC_URL="${PUBLIC_URL_WHITE}" \
  python main.py white > "${LOG_DIR}/white.log" 2>&1 &
WHITE_PID=$!

echo "Green PID: ${GREEN_PID}, log: ${LOG_DIR}/green.log"
echo "White PID: ${WHITE_PID}, log: ${LOG_DIR}/white.log"
echo "Expose/bind these ports via your ingress/Cloudflare tunnel so the PUBLIC_URLs are reachable."
echo "To stop: kill ${GREEN_PID} ${WHITE_PID}"
