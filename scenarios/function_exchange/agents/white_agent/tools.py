# -*- coding: utf-8 -*-
"""
Tools for the Function Exchange white agent that evaluates registered math
functions using canonical names provided in the registry.
"""

from __future__ import annotations

import sys
from pathlib import Path

import agentbeats as ab

# Comment: Add the scenario root to sys.path so shared helpers are importable.
SCENARIO_ROOT = Path(__file__).resolve().parents[2]
if str(SCENARIO_ROOT) not in sys.path:
    sys.path.insert(0, str(SCENARIO_ROOT))

from shared.functions_pool import evaluate_function, format_function_menu, get_function
from shared.logging_utils import setup_component_logger

# Comment: Dedicated file logger for the white agent.
white_logger = setup_component_logger(
    "function_exchange.white_agent", "function_exchange_white_agent.log"
)


# Comment: Provide a quick lookup of the registered functions for the LLM.
@ab.tool
def list_registered_functions() -> str:
    """
    Return a formatted list of all registered functions so the LLM can reason
    about canonical names versus their human descriptions.
    """
    registry_text = format_function_menu()
    white_logger.info("Registry requested:\n%s", registry_text)
    return registry_text


# Comment: Execute a registered function with the supplied x value.
@ab.tool
def call_registered_function(function_name: str, x: float) -> str:
    """
    Evaluate the requested function and return just the numeric value so the
    calling LLM can echo it back to the green agent.
    """
    try:
        fn = get_function(function_name)
    except ValueError as exc:
        white_logger.error("Invalid function '%s': %s", function_name, exc)
        return str(exc)

    result = evaluate_function(function_name, x)
    white_logger.info(
        "Function %s called with x=%s -> %s", fn.name, x, result
    )
    return str(result)

