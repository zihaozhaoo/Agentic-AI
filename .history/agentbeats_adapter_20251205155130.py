import os
import json
import uvicorn
import datetime
import tomllib
from typing import Optional, List, Any
import sys

# Agentic-AI imports
# Assuming this script is run from the root of Agentic-AI
from src.white_agent.baseline_agents import RegexBaselineAgent
from src.white_agent.data_structures import NaturalLanguageRequest, StructuredRequest

# AgentBeats imports
from agentbeats.agent_executor import AgentBeatsExecutor
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import TaskUpdater, InMemoryTaskStore
from a2a.types import AgentCard
from a2a.server.agent_execution import RequestContext

class CustomAgentExecutor(AgentBeatsExecutor):
    def __init__(self, agent_card_json, model_type, model_name, mcp_url_list=None, tool_list=None):
        # We don't need to initialize the parent fully if we override invoke_agent and don't use its main_agent
        # But it's safer to call super init
        super().__init__(agent_card_json, model_type, model_name, mcp_url_list, tool_list)
        
        # Initialize the specific agent
        # We might need config, but for baseline it's optional
        self.white_agent = RegexBaselineAgent()
        print(f"Initialized {self.white_agent.agent_name}")

    async def invoke_agent(self, context: RequestContext) -> str:
        user_input = context.get_user_input()
        print(f"Received input: {user_input}")

        # Create a NaturalLanguageRequest
        request_id = f"req_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
        request_time = datetime.datetime.now()
        
        nl_request = NaturalLanguageRequest(
            request_id=request_id,
            request_time=request_time,
            natural_language_text=user_input
        )

        # Parse the request
        try:
            # vehicle_database is None as per demo_baselines.py for RegexBaselineAgent parsing
            structured_request = self.white_agent.parse_request(nl_request, vehicle_database=None)
            
            # Convert to dict and then JSON string
            response_data = structured_request.to_dict()
            response_str = json.dumps(response_data, indent=2)
            return response_str
        except Exception as e:
            error_msg = f"Error processing request: {str(e)}"
            print(error_msg)
            return error_msg

def main():
    # Load agent card
    card_path = "agent_card.toml"
    if not os.path.exists(card_path):
        print(f"Error: {card_path} not found.")
        return

    with open(card_path, "rb") as f:
        agent_card_data = tomllib.load(f)

    # Create executor
    # We pass dummy model info as we are not using the LLM agent from SDK directly
    executor = CustomAgentExecutor(
        agent_card_json=agent_card_data,
        model_type="openai", 
        model_name="gpt-4o-mini", 
    )

    # Create app
    app = A2AStarletteApplication(
        agent_card=AgentCard(**agent_card_data),
        http_handler=DefaultRequestHandler(
            agent_executor=executor,
            task_store=InMemoryTaskStore(),
        ),
    ).build()

    # Run
    # Port should match what's in the agent card or be configurable
    port = 8001
    print(f"Starting agent on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
