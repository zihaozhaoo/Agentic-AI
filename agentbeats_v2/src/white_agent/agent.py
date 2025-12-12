"""Sample white agent (LLM echo) for v2 harness completeness."""

import tomllib
import dotenv
import uvicorn
import os
from pathlib import Path
import json
import math

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCard
from a2a.utils import new_agent_text_message
from litellm import completion

dotenv.load_dotenv()


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
            gt = payload.get("ground_truth") or {}
            req_id = payload.get("request_id", "")
            # Use ground truth origin/dest if available
            origin = gt.get("origin", {}) if isinstance(gt, dict) else {}
            dest = gt.get("destination", {}) if isinstance(gt, dict) else {}
            o_lat = origin.get("latitude", 40.75)
            o_lon = origin.get("longitude", -73.98)
            d_lat = dest.get("latitude", 40.75)
            d_lon = dest.get("longitude", -73.98)

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
            resp = {
                "parsed": {
                    "pickup_zone_id": origin.get("zone_id"),
                    "dropoff_zone_id": dest.get("zone_id"),
                    "pickup_zone": origin.get("zone_name"),
                    "dropoff_zone": dest.get("zone_name"),
                    "pickup_latitude": o_lat,
                    "pickup_longitude": o_lon,
                    "dropoff_latitude": d_lat,
                    "dropoff_longitude": d_lon,
                    "passenger_count": origin.get("passenger_count", 1),
                    "wheelchair_accessible": origin.get("wheelchair_accessible", False),
                    "shared_ride_ok": origin.get("shared_ride_ok", True),
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


def start_white_agent(agent_name="sample_white_agent", host="localhost", port=9102):
    host = os.environ.get("AGENT_HOST", host)
    port = int(os.environ.get("AGENT_PORT", port))
    public_url = os.environ.get("PUBLIC_URL", f"http://{host}:{port}")

    card = load_agent_card(agent_name, public_url)

    request_handler = DefaultRequestHandler(
        agent_executor=SampleWhiteExecutor(),
        task_store=InMemoryTaskStore(),
    )

    app = A2AStarletteApplication(
        agent_card=card,
        http_handler=request_handler,
    )

    uvicorn.run(app.build(), host=host, port=port)
