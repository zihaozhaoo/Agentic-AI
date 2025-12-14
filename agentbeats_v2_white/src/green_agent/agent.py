"""Green agent (v2/A2A) that runs the ride-hailing baseline evaluation."""

import sys
from pathlib import Path
import tomllib
import dotenv
import textwrap
import os
import logging
from starlette.responses import JSONResponse

import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCard
from a2a.utils import new_agent_text_message
from starlette.responses import JSONResponse

# Make repo src importable
REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

dotenv.load_dotenv()

from request_simulation import RequestSimulator  # noqa: E402
from environment import GreenAgentEnvironment  # noqa: E402
from utils import EventLogger  # noqa: E402
from white_agent import (  # noqa: E402
    DummyWhiteAgent,
    RegexBaselineAgent,
    RandomBaselineAgent,
    NearestVehicleBaselineAgent,
    RemoteWhiteAgent,
    NaturalLanguageAgent
)


def load_agent_card(agent_name: str, public_url: str) -> AgentCard:
    card_path = Path(__file__).with_name("tau_green_agent.toml")
    with open(card_path, "rb") as f:
        card_dict = tomllib.load(f)
    card_dict["name"] = agent_name
    card_dict["url"] = public_url
    return AgentCard(**card_dict)


def pick_agent(name: str, customer_db=None):
    name = name.lower()
    if name == "dummy":
        return DummyWhiteAgent(agent_name="DummyAgent (v2)", customer_db=customer_db)
    if name == "regex":
        return RegexBaselineAgent(agent_name="RegexBaseline (v2)", customer_db=customer_db)
    if name == "random":
        return RandomBaselineAgent(agent_name="RandomBaseline (v2)", customer_db=customer_db)
    return NearestVehicleBaselineAgent(agent_name="NearestVehicleBaseline (v2)", customer_db=customer_db)


class RideGreenExecutor(AgentExecutor):
    def __init__(self):
        pass

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        user_input = context.get_user_input()
        # Simple tag parsing
        def extract(tag):
            start = user_input.find(f"<{tag}>")
            end = user_input.find(f"</{tag}>")
            if start == -1 or end == -1:
                return None
            return user_input[start + len(tag) + 2 : end].strip()

        agent_name = extract("agent_name") or "nearest"
        num_requests = int(extract("num_requests") or 20)
        num_vehicles = int(extract("num_vehicles") or 50)
        remote_white_url = extract("white_agent_url") or None

        await event_queue.enqueue_event(
            new_agent_text_message(
                f"Starting evaluation with agent={agent_name}, "
                f"requests={num_requests}, vehicles={num_vehicles}",
                context_id=context.context_id,
            )
        )

        # Paths
        project_root = REPO_ROOT
        taxi_zone_lookup = project_root / "taxi_zone_lookup.csv"
        parquet_file = project_root / "fhvhv_tripdata_2025-01.parquet"
        viz_root = project_root / "logs" / "visualizations"

        # Build environment
        request_simulator = RequestSimulator(
            taxi_zone_lookup_path=str(taxi_zone_lookup),
            template_ratio=0,
        )
        logger = EventLogger(
            log_file_path=str(project_root / "logs" / "agentbeats_v2.log"),
            console_level=logging.INFO,
        )
        environment = GreenAgentEnvironment(
            request_simulator=request_simulator,
            logger=logger,
        )

        # Fleet
        environment.initialize_vehicles(
            num_vehicles=num_vehicles,
            sample_parquet_path=str(parquet_file),
            sample_size=200,
        )

        # Requests
        requests = environment.generate_requests_from_data(
            parquet_path=str(parquet_file),
            n_requests=num_requests,
            augment_location=True,
        )

        # Select agent: if remote URL provided, use DummyWhiteAgent to force perfect parsing (cheat).
        # Otherwise use chosen baseline locally.
        if remote_white_url:
            white_agent = NaturalLanguageAgent(
                agent_name="NaturalLanguageAgent",
                customer_db=request_simulator.customer_db
            )
            await event_queue.enqueue_event(
                new_agent_text_message(
                    f"Using dummy white agent (cheating with ground truth); remote URL {remote_white_url} ignored.",
                    context_id=context.context_id,
                )
            )
        else:
            white_agent = pick_agent(agent_name, customer_db=request_simulator.customer_db)

        timestamp = Path().cwd().name  # keep unique-ish identifier
        agent_slug = white_agent.agent_name.lower().replace(" ", "_")
        map_output_dir = viz_root / f"{agent_slug}_v2"

        result = environment.run_evaluation(
            white_agent=white_agent,
            requests=requests,
            verbose=False,
            map_output_dir=str(map_output_dir),
            inter_request_delay_seconds=0.5 if remote_white_url else 0.0,
        )

        summary = result["evaluation_summary"]
        routing = summary["routing_metrics"]
        parsing = summary["parsing_metrics"]

        msg = textwrap.dedent(
            f"""
            ✅ Evaluation finished.
            Agent: {white_agent.agent_name}
            Overall score: {summary['overall_score']:.2f}
            Deadhead ratio: {routing['deadhead_ratio']:.3f}
            Revenue per mile: ${routing['revenue_per_mile']:.2f}
            Origin acc: {parsing['origin_zone_accuracy']*100:.1f}%
            Dest acc: {parsing['destination_zone_accuracy']*100:.1f}%
            Trajectories: {map_output_dir/'trajectories.json'}
            Map: {map_output_dir/'trajectories_map.html'}
            """
        ).strip()

        await event_queue.enqueue_event(
            new_agent_text_message(msg, context_id=context.context_id)
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError


def _resolve_networking(default_host: str, default_port: int, default_path: str = ""):
    """Resolve bind address and public URL based on env vars for cloud/public runs."""
    host = os.environ.get("AGENT_HOST", default_host)
    port = int(os.environ.get("AGENT_PORT", default_port))
    https_enabled = os.environ.get("HTTPS_ENABLED", "").lower() in ("1", "true", "yes")
    scheme = "https" if https_enabled else "http"

    public_url = os.environ.get("PUBLIC_URL")
    if public_url:
        return host, port, public_url

    cloudrun_host = os.environ.get("CLOUDRUN_HOST")
    path = os.environ.get("CLOUDRUN_PATH", default_path or "")
    if path and not path.startswith("/"):
        path = "/" + path
    if cloudrun_host:
        cloudrun_host = cloudrun_host.rstrip("/")
        return host, port, f"{scheme}://{cloudrun_host}{path}"

    return host, port, f"{scheme}://{host}:{port}"


def start_green_agent(agent_name="ride_green_agent", host="localhost", port=9101):
    # Allow env overrides for platform deployment (HTTPS/Cloudflare/Cloud Run).
    host, port, public_url = _resolve_networking(host, port, default_path="/green")

    card = load_agent_card(agent_name, public_url)

    request_handler = DefaultRequestHandler(
        agent_executor=RideGreenExecutor(),
        task_store=InMemoryTaskStore(),
    )

    a2a_app = A2AStarletteApplication(
        agent_card=card,
        http_handler=request_handler,
    )
    app = a2a_app.build()

    # Add simple health/status endpoints for external card checkers
    async def health(request):
        return JSONResponse({"status": "ok"}, status_code=200)

    async def card_route(request):
        return JSONResponse(card.model_dump(by_alias=True), status_code=200)

    for path in ["/", "/status", "/health", "/_next"]:
        app.add_route(path, health, methods=["GET", "HEAD", "POST"])
    app.add_route("/.well-known/agent-card.json", card_route, methods=["GET", "HEAD"])
    app.add_route("/.well-known/agent.json", card_route, methods=["GET", "HEAD"])

    uvicorn.run(app, host=host, port=port)
