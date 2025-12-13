#!/usr/bin/env bash
# Entry point used by `agentbeats run_ctrl` to launch the ride-hailing white agent.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# AGENT_HOST/AGENT_PORT/PUBLIC_URL/HTTPS_ENABLED/CLOUDRUN_HOST are read by start_white_agent.
python main.py white
