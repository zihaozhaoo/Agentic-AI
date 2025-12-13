# -*- coding: utf-8 -*-
"""
Battle orchestration helper that drives the interaction between the green and
white agents in the Function Exchange scenario.
"""

from __future__ import annotations

import json
import math
import random
import re
from dataclasses import dataclass
from typing import Dict, Optional

from agentbeats.logging import (
    BattleContext,
    record_agent_action,
    record_battle_event,
    record_battle_result,
)
from agentbeats.utils.agents import send_message_to_agent

from .functions_pool import RegisteredFunction, choose_function, describe_functions
from .logging_utils import setup_component_logger


# Comment: Track green agent orchestration state across tools.
@dataclass
class OrchestratorState:
    """
    Container that keeps the current BattleContext and metadata about the white
    agent that participates in the exchange.
    """

    battle_context: Optional[BattleContext] = None
    participant_contexts: Dict[str, Dict[str, str]] | None = None
    opponent_infos: Dict[str, Dict] | None = None
    white_agent_url: Optional[str] = None
    white_agent_name: Optional[str] = None


# Comment: Create a dedicated logger for the orchestration module.
orchestrator_logger = setup_component_logger(
    "function_exchange.orchestrator", "function_exchange_orchestrator.log"
)


# Comment: Encapsulate the full send-and-verify process used by the green agent.
class FunctionExchangeOrchestrator:
    """
    Provides a higher level orchestrate_round entry point so the green agent tool
    stays tiny and the heavy lifting (prompt building, verification, logging) is
    unit-testable.
    """

    def __init__(self) -> None:
        self.state = OrchestratorState()

    # Comment: Update state when the backend sends a battle_start message.
    def ingest_battle_start(self, payload: Dict) -> str:
        """
        Accept a battle_start payload, build a BattleContext, and locate the
        white agent's URL + metadata.
        """
        if payload.get("type") != "battle_start":
            raise ValueError("Payload is not a battle_start message.")

        green_ctx_data = payload.get("green_battle_context") or {}
        battle_id = green_ctx_data.get("battle_id") or payload.get("battle_id")
        backend_url = green_ctx_data.get("backend_url", "")
        agent_name = green_ctx_data.get("agent_name", "green_agent")

        if not (battle_id and backend_url):
            raise ValueError("Battle start payload missing battle_id or backend_url.")

        battle_context = BattleContext(
            battle_id=battle_id, backend_url=backend_url, agent_name=agent_name
        )

        participant_contexts = payload.get("red_battle_contexts") or {}
        opponent_infos = {entry["agent_url"]: entry for entry in payload.get("opponent_infos", []) if entry.get("agent_url")}

        if not participant_contexts:
            raise ValueError("Battle start payload missing participant contexts.")

        # Comment: Prefer explicit opponent info to surface the friendly name.
        selected_url, selected_name = None, None
        for url, ctx in participant_contexts.items():
            selected_url = url
            selected_name = ctx.get("agent_name")
            if opponent_infos.get(url, {}).get("alias"):
                selected_name = opponent_infos[url]["alias"]
            break

        if not selected_url:
            raise ValueError("Unable to resolve white agent URL from payload.")

        self.state = OrchestratorState(
            battle_context=battle_context,
            participant_contexts=participant_contexts,
            opponent_infos=opponent_infos,
            white_agent_url=selected_url,
            white_agent_name=selected_name or "white_agent",
        )

        orchestrator_logger.info(
            "Battle %s initialized. White agent %s at %s",
            battle_id,
            self.state.white_agent_name,
            self.state.white_agent_url,
        )

        record_battle_event(
            battle_context,
            "Function Exchange battle initialized",
            detail={
                "white_agent_url": self.state.white_agent_url,
                "white_agent_name": self.state.white_agent_name,
                "available_functions": describe_functions(),
            },
        )

        return f"Battle context stored for {battle_id} with white agent {self.state.white_agent_name}"

    # Comment: Main entry point invoked by the green agent tool to run a single round.
    async def orchestrate_round(
        self,
        requested_function: str | None = None,
        supplied_x: float | None = None,
        seed: int | None = None,
    ) -> str:
        """
        Run a full verification round: pick a function/x, send the description
        and number to the white agent, then validate the response.
        """
        if not (self.state.battle_context and self.state.white_agent_url):
            raise RuntimeError("Battle context not initialized. Call ingest_battle_start first.")

        fn_spec = choose_function(requested_function, seed=seed)
        x_value = supplied_x if supplied_x is not None else fn_spec.sample_input(random.Random(seed))
        orchestrator_logger.info(
            "Selected function %s and x=%s for battle %s",
            fn_spec.name,
            x_value,
            self.state.battle_context.battle_id,
        )

        request_text = self._build_white_agent_prompt(fn_spec, x_value)
        await self._log_start(fn_spec, x_value, request_text)

        try:
            response_text = await send_message_to_agent(self.state.white_agent_url, request_text)
        except Exception as exc:
            orchestrator_logger.exception("Failed to reach white agent: %s", exc)
            raise

        orchestrator_logger.info("White agent response: %s", response_text)

        verification = self._verify_response(fn_spec, x_value, response_text)
        await self._record_round_result(fn_spec, x_value, response_text, verification)

        return json.dumps(verification, indent=2)

    # Comment: Build the user-friendly instructions sent to the white agent.
    def _build_white_agent_prompt(self, fn_spec: RegisteredFunction, x_value: float) -> str:
        """
        Render a plain text instruction that contains the number and a narrative
        description of the target function (without referencing canonical names).
        """
        return (
            "Function Exchange Task:\n"
            f"- Input number x: {x_value}\n"
            f"- Function description: {fn_spec.description}\n\n"
            "Steps:\n"
            "1. Identify which registered function matches the description above.\n"
            "2. Execute the exact registered function using your tools.\n"
            "3. Respond ONLY with f(x) as a numeric value. Omit extra narration."
        )

    # Comment: Convert the white agent's text response into a numeric value and compare.
    def _verify_response(
        self, fn_spec: RegisteredFunction, x_value: float, response_text: str
    ) -> Dict[str, object]:
        """
        Attempt to parse a floating point number from the response and compare
        it to the ground truth with a small tolerance.
        """
        expected = fn_spec.evaluate(x_value)
        predicted = self._extract_first_float(response_text)
        matches = predicted is not None and math.isclose(
            predicted, expected, rel_tol=1e-6, abs_tol=1e-4
        )
        return {
            "function": fn_spec.name,
            "x": x_value,
            "expected": expected,
            "predicted": predicted,
            "raw_response": response_text,
            "match": matches,
        }

    # Comment: Regex helper that extracts the first float present in the response.
    @staticmethod
    def _extract_first_float(text: str) -> Optional[float]:
        """
        Extract the first decimal or integer (with optional sign) present in the
        supplied text. Returns None when no number can be located.
        """
        if not text:
            return None
        match = re.search(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", text)
        if not match:
            return None
        try:
            return float(match.group())
        except ValueError:
            return None

    # Comment: Emit backend logs for the beginning of a round.
    async def _log_start(self, fn_spec: RegisteredFunction, x_value: float, prompt: str) -> None:
        """
        Persist structured logs describing which function/x pair was selected and
        include the outgoing prompt for debugging.
        """
        if self.state.battle_context:
            record_agent_action(
                self.state.battle_context,
                "function_exchange_round_start",
                detail={
                    "function": fn_spec.name,
                    "x": x_value,
                    "prompt": prompt,
                },
            )

    # Comment: Persist the verification result (event + result markers).
    async def _record_round_result(
        self,
        fn_spec: RegisteredFunction,
        x_value: float,
        response_text: str,
        verification: Dict[str, object],
    ) -> None:
        """
        Send the verification summary to the backend and emit an explicit battle
        result log so the UI can highlight whether the white agent succeeded.
        """
        if not self.state.battle_context:
            return

        record_battle_event(
            self.state.battle_context,
            "White agent completed a function evaluation",
            detail={
                "function": fn_spec.name,
                "x": x_value,
                "white_agent_response": response_text,
                "predicted_value": verification["predicted"],
                "expected_value": verification["expected"],
                "match": verification["match"],
            },
        )

        record_battle_result(
            self.state.battle_context,
            message="Function evaluation round finished",
            winner="white_agent" if verification["match"] else "green_agent",
            detail=verification,
        )


# Comment: Shared orchestrator instance consumed by green_agent.tools.
orchestrator = FunctionExchangeOrchestrator()
