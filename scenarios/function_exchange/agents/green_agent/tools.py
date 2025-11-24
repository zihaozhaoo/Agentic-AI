# -*- coding: utf-8 -*-
"""
Tools for the Function Exchange green agent responsible for orchestrating math
function verification rounds with the white agent.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import agentbeats as ab

# Comment: Expose shared scenario helpers (function registry + orchestrator).
SCENARIO_ROOT = Path(__file__).resolve().parents[2]
if str(SCENARIO_ROOT) not in sys.path:
    sys.path.insert(0, str(SCENARIO_ROOT))

from shared.logging_utils import setup_component_logger
from shared.orchestration import orchestrator

# Comment: Configure dedicated logger for the green agent.
green_logger = setup_component_logger(
    "function_exchange.green_agent", "function_exchange_green_agent.log"
)


# Comment: Parse battle_start messages from the backend and hydrate orchestrator state.
@ab.tool
def handle_incoming_message(message: str) -> str:
    """
    Store the latest battle context plus the white agent metadata. This MUST be
    invoked as soon as any new message from the backend arrives.
    """
    try:
        payload = json.loads(message)
    except json.JSONDecodeError as exc:
        error_msg = f"Invalid JSON payload: {exc}"
        green_logger.error(error_msg)
        return error_msg

    try:
        ack = orchestrator.ingest_battle_start(payload)
        green_logger.info("Battle context registered: %s", ack)
        return ack
    except Exception as exc:  # pragma: no cover - defensive logging
        error_msg = f"Failed to ingest battle start message: {exc}"
        green_logger.exception(error_msg)
        return error_msg


# Comment: Run a complete round that challenges the white agent and verifies the reply.
@ab.tool
async def start_function_exchange(
    function_name: Optional[str] = None,
    x: Optional[float] = None,
    seed: Optional[int] = None,
) -> str:
    """
    Kick off a function exchange round. Optional arguments allow deterministic
    replay for debugging (e.g., pass both function_name and x).
    """
    try:
        result = await orchestrator.orchestrate_round(
            requested_function=function_name, supplied_x=x, seed=seed
        )
        green_logger.info("Verification summary: %s", result)
        return result
    except Exception as exc:  # pragma: no cover - defensive logging
        error_msg = f"Round execution failed: {exc}"
        green_logger.exception(error_msg)
        return error_msg

