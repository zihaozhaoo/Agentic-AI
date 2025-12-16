"""Sample white agent (LLM echo) for v2 harness completeness."""

import tomllib
import dotenv
import uvicorn
import os
import sys
from pathlib import Path
import json
import math
from datetime import datetime
from starlette.responses import JSONResponse

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCard
from a2a.utils import new_agent_text_message
from litellm import completion

# Make repo src importable
REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

dotenv.load_dotenv()

# Import NaturalLanguageAgent and related data structures
from white_agent import NaturalLanguageAgent, NaturalLanguageRequest, Location


def load_agent_card(agent_name: str, public_url: str) -> AgentCard:
    card_path = Path(__file__).with_name("general_white_agent.toml")
    with open(card_path, "rb") as f:
        card_dict = tomllib.load(f)
    card_dict["name"] = agent_name
    card_dict["url"] = public_url
    return AgentCard(**card_dict)


class SampleWhiteExecutor(AgentExecutor):
    def __init__(self):
        self.ctx_history = {}
        # Initialize NaturalLanguageAgent for parsing
        self.nl_agent = NaturalLanguageAgent(agent_name="NaturalLanguageAgent (v2)")

    def _parse_json_from_input(self, text: str):
        start = text.find("<json>")
        end = text.find("</json>")
        if start != -1 and end != -1:
            text = text[start + 6 : end]
        try:
            return json.loads(text)
        except Exception:
            return None

    def _dist(self, lat1, lon1, lat2, lon2):
        lat_diff = lat2 - lat1
        lon_diff = lon2 - lon1
        return math.hypot(lat_diff, lon_diff)

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        user_input = context.get_user_input()
        payload = self._parse_json_from_input(user_input)

        # If JSON payload provided, act as routing agent
        if payload and isinstance(payload, dict) and "fleet" in payload:
            fleet = payload.get("fleet") or []
            req_id = payload.get("request_id", "")
            request_text = payload.get("request_text", "")

            # Create NaturalLanguageRequest object
            nl_request = NaturalLanguageRequest(
                request_id=req_id,
                request_time=datetime.now(),
                natural_language_text=request_text
            )

            # Use NaturalLanguageAgent to parse the request
            try:
                # NaturalLanguageAgent.parse_request expects a VehicleDatabase, but we don't have one
                # So we'll call the internal parsing methods directly
                parsed = self.nl_agent.parse_request(nl_request, vehicle_database=None)

                o_lat = parsed.origin.latitude
                o_lon = parsed.origin.longitude
                d_lat = parsed.destination.latitude
                d_lon = parsed.destination.longitude

            except Exception as e:
                # If parsing fails, use fallback coordinates
                print(f"NaturalLanguageAgent parsing failed: {e}")
                o_lat, o_lon = 40.75, -73.98
                d_lat, d_lon = 40.75, -73.98
                parsed = None

            # pick nearest idle/available vehicle
            best_id = None
            best_dist = math.inf
            for v in fleet:
                if v.get("status") not in ("idle", "available", "en_route_to_pickup", "IDLE"):
                    continue
                lat = v.get("latitude")
                lon = v.get("longitude")
                if lat is None or lon is None:
                    continue
                dist = self._dist(o_lat, o_lon, lat, lon)
                if dist < best_dist:
                    best_dist = dist
                    best_id = v.get("vehicle_id")

            # rough miles
            deadhead_miles = best_dist * 69.0 if best_id else 1.0
            trip_dist = self._dist(o_lat, o_lon, d_lat, d_lon) * 69.0

            # Build response from parsed data
            resp = {
                "parsed": {
                    "pickup_zone_id": parsed.origin.zone_id if parsed else None,
                    "dropoff_zone_id": parsed.destination.zone_id if parsed else None,
                    "pickup_zone": parsed.origin.zone_name if parsed else None,
                    "dropoff_zone": parsed.destination.zone_name if parsed else None,
                    "pickup_latitude": o_lat,
                    "pickup_longitude": o_lon,
                    "dropoff_latitude": d_lat,
                    "dropoff_longitude": d_lon,
                    "passenger_count": parsed.passenger_count if parsed else 1,
                    "wheelchair_accessible": parsed.wheelchair_accessible if parsed else False,
                    "shared_ride_ok": parsed.shared_ride_ok if parsed else True,
                },
                "routing": {
                    "vehicle_id": best_id,
                    "estimated_pickup_distance_miles": deadhead_miles,
                    "estimated_trip_distance_miles": trip_dist,
                },
                "request_id": req_id,
            }
            text = f"<json>{json.dumps(resp)}</json>"
            await event_queue.enqueue_event(
                new_agent_text_message(text, context_id=context.context_id)
            )
            return

        # Fallback: echo via LLM
        ctx_id = context.context_id
        if ctx_id not in self.ctx_history:
            self.ctx_history[ctx_id] = []
        history = self.ctx_history[ctx_id]
        history.append({"role": "user", "content": user_input})

        resp = completion(
            messages=history,
            model="openai/gpt-4o",
            custom_llm_provider="openai",
            temperature=0.0,
        )
        next_msg = resp.choices[0].message.model_dump()
        history.append({"role": "assistant", "content": next_msg["content"]})

        await event_queue.enqueue_event(
            new_agent_text_message(next_msg["content"], context_id=ctx_id)
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError


def _resolve_networking(default_host: str, default_port: int, default_path: str = ""):
    """Resolve bind address and public URL based on env vars for cloud/public runs."""
    host = os.environ.get("AGENT_HOST", default_host)
    port = int(os.environ.get("AGENT_PORT", default_port))
    https_enabled = os.environ.get("HTTPS_ENABLED", "").lower() in ("1", "true", "yes")
    scheme = "https" if https_enabled else "http"

    # Priority 1: AGENT_URL set by controller (for agentbeats run_ctrl mode)
    agent_url = os.environ.get("AGENT_URL")
    if agent_url:
        return host, port, agent_url

    # Priority 2: PUBLIC_URL explicitly set by user
    public_url = os.environ.get("PUBLIC_URL")
    if public_url:
        return host, port, public_url

    # Priority 3: Construct from CLOUDRUN_HOST + CLOUDRUN_PATH
    cloudrun_host = os.environ.get("CLOUDRUN_HOST")
    path = os.environ.get("CLOUDRUN_PATH", default_path or "")
    if path and not path.startswith("/"):
        path = "/" + path
    if cloudrun_host:
        cloudrun_host = cloudrun_host.rstrip("/")
        return host, port, f"{scheme}://{cloudrun_host}{path}"

    # Priority 4: Default to localhost
    return host, port, f"{scheme}://{host}:{port}"


def start_white_agent(agent_name="sample_white_agent", host="localhost", port=9102):
    host, port, public_url = _resolve_networking(host, port, default_path="/white")

    card = load_agent_card(agent_name, public_url)

    request_handler = DefaultRequestHandler(
        agent_executor=SampleWhiteExecutor(),
        task_store=InMemoryTaskStore(),
    )

    a2a_app = A2AStarletteApplication(
        agent_card=card,
        http_handler=request_handler,
    )
    app = a2a_app.build()

    async def health(request):
        return JSONResponse({"status": "ok"}, status_code=200)

    async def card_route(request):
        return JSONResponse(card.model_dump(by_alias=True), status_code=200)

    for path in ["/", "/status", "/health", "/_next"]:
        app.add_route(path, health, methods=["GET", "HEAD", "POST"])
    app.add_route("/.well-known/agent-card.json", card_route, methods=["GET", "HEAD"])
    app.add_route("/.well-known/agent.json", card_route, methods=["GET", "HEAD"])

    uvicorn.run(app, host=host, port=port)
