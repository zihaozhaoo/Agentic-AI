"""
Green Agent Server for AgentBeats Platform

This server exposes the NYC ride-hailing green agent (orchestrator/evaluator)
via the A2A protocol for integration with AgentBeats.
"""

import os
import json
import uvicorn
import datetime
import tomllib
from typing import Optional, List, Any
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Agentic-AI imports
from request_simulation import RequestSimulator
from environment import GreenAgentEnvironment
from white_agent import NaturalLanguageRequest, StructuredRequest
from vehicle_system import VehicleDatabase
from evaluation import Evaluator
from utils import EventLogger

# AgentBeats imports
from agentbeats.agent_executor import AgentBeatsExecutor
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import TaskUpdater, InMemoryTaskStore
from a2a.types import AgentCard
from a2a.server.agent_execution import RequestContext


class GreenAgentExecutor(AgentBeatsExecutor):
    """Green Agent Executor for ride-hailing evaluation orchestration."""

    def __init__(self, agent_card_json, model_type, model_name, mcp_url_list=None, tool_list=None):
        super().__init__(agent_card_json, model_type, model_name, mcp_url_list, tool_list)

        # Initialize paths
        self.project_root = Path(__file__).parent
        self.taxi_zone_lookup = str(self.project_root / "taxi_zone_lookup.csv")
        self.parquet_file = str(self.project_root / "fhvhv_tripdata_2025-01.parquet")

        # Initialize request simulator
        self.request_simulator = RequestSimulator(
            taxi_zone_lookup_path=self.taxi_zone_lookup,
            template_ratio=1.0,  # Use templates for deterministic generation
        )

        # Initialize green agent environment
        self.environment = GreenAgentEnvironment(
            request_simulator=self.request_simulator,
            logger=EventLogger()
        )

        # Session state
        self.session_state = {
            "initialized": False,
            "vehicles_ready": False,
            "requests_generated": False,
            "current_battle": None,
            "white_agents": {},
            "results": {}
        }

        print(f"✓ Initialized Green Agent (NYC Ride-Hailing Orchestrator)")
        print(f"  - Role: Battle orchestrator and evaluator")
        print(f"  - Capabilities: Request generation, fleet management, performance scoring")

    async def invoke_agent(self, context: RequestContext) -> str:
        """
        Process incoming messages and orchestrate evaluation.

        Expected message formats:
        1. "initialize_battle" - Set up new evaluation session
        2. "register_white_agent" - Register a white agent for battle
        3. "start_battle" - Begin the evaluation
        4. "submit_response" - White agent submits parsing/routing response
        5. "get_results" - Retrieve battle results
        """
        user_input = context.get_user_input()
        print(f"\n[Green Agent] Received: {user_input[:200]}...")

        try:
            # Try to parse as JSON command
            try:
                command = json.loads(user_input)
                command_type = command.get("command", "")
            except json.JSONDecodeError:
                # Treat as natural language command
                command_type = self._parse_nl_command(user_input)
                command = {"command": command_type, "input": user_input}

            # Route to appropriate handler
            if command_type == "initialize_battle":
                response = await self._initialize_battle(command)
            elif command_type == "register_white_agent":
                response = await self._register_white_agent(command)
            elif command_type == "start_battle":
                response = await self._start_battle(command)
            elif command_type == "submit_response":
                response = await self._process_white_agent_response(command)
            elif command_type == "get_results":
                response = await self._get_results(command)
            elif command_type == "get_status":
                response = await self._get_status()
            else:
                response = {
                    "status": "ready",
                    "message": "Green Agent ready for evaluation orchestration",
                    "available_commands": [
                        "initialize_battle",
                        "register_white_agent",
                        "start_battle",
                        "submit_response",
                        "get_results",
                        "get_status"
                    ],
                    "session_state": self.session_state,
                    "timestamp": datetime.datetime.now().isoformat()
                }

            return json.dumps(response, indent=2)

        except Exception as e:
            error_response = {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.datetime.now().isoformat()
            }
            print(f"[Green Agent] Error: {e}")
            import traceback
            traceback.print_exc()
            return json.dumps(error_response, indent=2)

    def _parse_nl_command(self, text: str) -> str:
        """Parse natural language to command type."""
        text_lower = text.lower()

        if "initialize" in text_lower or "setup" in text_lower or "start new" in text_lower:
            return "initialize_battle"
        elif "register" in text_lower:
            return "register_white_agent"
        elif "start" in text_lower or "begin" in text_lower:
            return "start_battle"
        elif "submit" in text_lower or "response" in text_lower:
            return "submit_response"
        elif "results" in text_lower or "scores" in text_lower:
            return "get_results"
        elif "status" in text_lower:
            return "get_status"
        else:
            return "unknown"

    async def _initialize_battle(self, command: dict) -> dict:
        """Initialize a new evaluation battle."""
        print("[Green Agent] Initializing battle...")

        num_vehicles = command.get("num_vehicles", 100)
        num_requests = command.get("num_requests", 10)

        # Initialize vehicle fleet
        self.environment.initialize_vehicles(
            num_vehicles=num_vehicles,
            wheelchair_accessible_ratio=0.1,
            sample_parquet_path=self.parquet_file,
            sample_size=1000
        )

        # Generate requests
        requests = self.environment.generate_requests_from_data(
            parquet_path=self.parquet_file,
            n_requests=num_requests,
            augment_location=False
        )

        # Update session state
        battle_id = f"battle_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.session_state.update({
            "initialized": True,
            "vehicles_ready": True,
            "requests_generated": True,
            "current_battle": {
                "battle_id": battle_id,
                "num_vehicles": num_vehicles,
                "num_requests": len(requests),
                "requests": requests,
                "start_time": datetime.datetime.now().isoformat()
            },
            "white_agents": {},
            "results": {}
        })

        print(f"✓ Battle initialized: {battle_id}")
        print(f"  - Vehicles: {num_vehicles}")
        print(f"  - Requests: {len(requests)}")

        return {
            "status": "success",
            "battle_id": battle_id,
            "num_vehicles": num_vehicles,
            "num_requests": len(requests),
            "message": f"Battle environment initialized with {num_vehicles} vehicles and {len(requests)} requests",
            "fleet_stats": self.environment.vehicle_database.get_fleet_statistics()
        }

    async def _register_white_agent(self, command: dict) -> dict:
        """Register a white agent for the battle."""
        agent_id = command.get("agent_id", f"agent_{len(self.session_state['white_agents'])}")
        agent_name = command.get("agent_name", agent_id)
        agent_url = command.get("agent_url", "")

        self.session_state["white_agents"][agent_id] = {
            "agent_id": agent_id,
            "agent_name": agent_name,
            "agent_url": agent_url,
            "registered_at": datetime.datetime.now().isoformat()
        }

        print(f"✓ Registered white agent: {agent_name} ({agent_id})")

        return {
            "status": "success",
            "message": f"White agent '{agent_name}' registered successfully",
            "agent_id": agent_id,
            "total_agents": len(self.session_state["white_agents"])
        }

    async def _start_battle(self, command: dict) -> dict:
        """Start the evaluation battle."""
        if not self.session_state.get("initialized"):
            return {
                "status": "error",
                "message": "Battle not initialized. Run initialize_battle first."
            }

        battle = self.session_state["current_battle"]

        # Return first request for white agents to process
        first_request = battle["requests"][0]

        return {
            "status": "battle_started",
            "battle_id": battle["battle_id"],
            "message": "Battle started. White agents should begin processing requests.",
            "first_request": {
                "request_id": first_request.get("trip_id"),
                "natural_language": first_request.get("request"),
                "pickup_zone": first_request.get("pickup_zone"),
                "dropoff_zone": first_request.get("dropoff_zone"),
                "request_time": str(first_request.get("request_time"))
            },
            "total_requests": len(battle["requests"]),
            "available_vehicles": self.environment.vehicle_database.get_fleet_statistics()["available_vehicles"]
        }

    async def _process_white_agent_response(self, command: dict) -> dict:
        """Process a response from a white agent."""
        agent_id = command.get("agent_id")
        request_id = command.get("request_id")
        parsed_request = command.get("parsed_request", {})
        routing_decision = command.get("routing_decision", {})

        # Store response
        if agent_id not in self.session_state["results"]:
            self.session_state["results"][agent_id] = []

        self.session_state["results"][agent_id].append({
            "request_id": request_id,
            "parsed_request": parsed_request,
            "routing_decision": routing_decision,
            "received_at": datetime.datetime.now().isoformat()
        })

        return {
            "status": "success",
            "message": f"Response recorded for agent {agent_id}",
            "requests_processed": len(self.session_state["results"].get(agent_id, []))
        }

    async def _get_results(self, command: dict = None) -> dict:
        """Get battle results and scores."""
        if not self.session_state.get("current_battle"):
            return {
                "status": "error",
                "message": "No active battle"
            }

        battle = self.session_state["current_battle"]
        results = self.session_state["results"]

        # Calculate scores for each agent
        agent_scores = {}
        for agent_id, responses in results.items():
            # Simplified scoring
            agent_scores[agent_id] = {
                "agent_id": agent_id,
                "total_requests": len(responses),
                "score": len(responses) * 10,  # Placeholder scoring
                "metrics": {
                    "requests_processed": len(responses),
                    "success_rate": 1.0  # Placeholder
                }
            }

        return {
            "status": "success",
            "battle_id": battle["battle_id"],
            "agent_scores": agent_scores,
            "total_requests": battle["num_requests"],
            "total_vehicles": battle["num_vehicles"]
        }

    async def _get_status(self) -> dict:
        """Get current green agent status."""
        return {
            "status": "active",
            "role": "Green Agent (Orchestrator & Evaluator)",
            "session_state": self.session_state,
            "capabilities": [
                "Battle initialization and management",
                "Request generation from NYC trip data",
                "Vehicle fleet simulation",
                "White agent evaluation and scoring",
                "Performance metrics calculation"
            ],
            "timestamp": datetime.datetime.now().isoformat()
        }


def main():
    # Load agent card
    card_path = "green_agent_card.toml"
    if not os.path.exists(card_path):
        print(f"Error: {card_path} not found.")
        print("Please ensure green_agent_card.toml is in the current directory.")
        return

    with open(card_path, "rb") as f:
        agent_card_data = tomllib.load(f)

    # Create executor
    executor = GreenAgentExecutor(
        agent_card_json=agent_card_data,
        model_type="openai",
        model_name="gpt-4o-mini",
    )

    # Create A2A app
    app = A2AStarletteApplication(
        agent_card=AgentCard(**agent_card_data),
        http_handler=DefaultRequestHandler(
            agent_executor=executor,
            task_store=InMemoryTaskStore(),
        ),
    ).build()

    # Run on port 8002 (different from white agent on 8001)
    port = 8002
    print("\n" + "="*80)
    print("NYC RIDE-HAILING GREEN AGENT SERVER")
    print("="*80)
    print(f"  Green Agent (Orchestrator): http://localhost:{port}")
    print(f"  White Agent (Parser):       http://localhost:8001")
    print(f"  AgentBeats Platform:        http://localhost:9000 (backend)")
    print(f"                              http://localhost:5173 (frontend)")
    print("="*80)
    print("\nStarting server...")
    print()

    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
