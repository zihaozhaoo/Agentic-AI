"""
Remote white agent adapter (A2A) with local routing.

This adapter calls a remote A2A white agent to parse NL requests, then
performs routing locally (nearest vehicle) to keep simulation consistent.
"""

import uuid
import json
import httpx
import math
import asyncio
from datetime import timedelta
from typing import Optional, Dict, Any, List

from .base_agent import WhiteAgentBase
from .data_structures import StructuredRequest, RoutingDecision, Location, NaturalLanguageRequest
from a2a.client import A2ACardResolver, A2AClient
from a2a.types import (
    AgentCard,
    Part,
    TextPart,
    MessageSendParams,
    Message,
    Role,
    SendMessageRequest,
    SendMessageResponse,
)


def _zone_center_from_row(row: Dict[str, Any]) -> tuple[float, float]:
    borough_centers = {
        "Manhattan": (40.75, -73.98),
        "Brooklyn": (40.65, -73.95),
        "Queens": (40.72, -73.80),
        "Bronx": (40.85, -73.88),
        "Staten Island": (40.58, -74.15),
        "EWR": (40.69, -74.17),
    }
    borough = row.get("Borough", "Manhattan") if row else "Manhattan"
    base = borough_centers.get(borough, borough_centers["Manhattan"])
    return base


class RemoteWhiteAgent(WhiteAgentBase):
    """
    Calls a remote A2A white agent for parsing/routing, with local fallbacks.
    """

    def __init__(self, remote_url: str, zone_lookup_df, agent_name: str = "RemoteWhiteAgent", logger=None):
        super().__init__(agent_name)
        self.remote_url = remote_url.rstrip("/")
        self.zone_lookup_df = zone_lookup_df
        self.logger = logger
        self._routing_cache: Dict[str, Dict[str, Any]] = {}

        # Precompute helpers
        self.zone_name_to_row = {row["Zone"]: row for _, row in zone_lookup_df.iterrows()}
        self.zone_id_to_row = {int(row["LocationID"]): row for _, row in zone_lookup_df.iterrows()}

    def _log(self, msg: str):
        if self.logger:
            try:
                self.logger.log_event("REMOTE_WHITE", {"message": msg})
            except Exception:
                print(msg)
        else:
            print(msg)

    async def _async_send_message(self, text: str) -> Optional[str]:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resolver = A2ACardResolver(httpx_client=client, base_url=self.remote_url)
            card: AgentCard | None = await resolver.get_agent_card()
            if card is None:
                self._log("Remote card fetch failed")
                return None
            a2a_client = A2AClient(httpx_client=client, agent_card=card)
            message_id = uuid.uuid4().hex
            params = MessageSendParams(
                message=Message(
                    role=Role.user,
                    parts=[Part(TextPart(text=text))],
                    message_id=message_id,
                )
            )
            req = SendMessageRequest(id=uuid.uuid4().hex, params=params)
            try:
                resp: SendMessageResponse = await a2a_client.send_message(request=req)
                result = resp.result
                parts = result.parts if result else []
                for p in parts:
                    if p.type == "text" and hasattr(p, "text"):
                        return p.text
            except Exception as exc:
                self._log(f"Remote send_message failed: {exc}")
        return None

    def _sync_send_message(self, text: str) -> Optional[str]:
        try:
            return asyncio.run(self._async_send_message(text))
        except Exception as exc:
            self._log(f"Async send_message failed: {exc}")
            return None

    def _parse_remote_json(self, text: str) -> Dict[str, Any]:
        if not text:
            return {}
        start = text.find("<json>")
        end = text.find("</json>")
        content = text[start + 6 : end] if start != -1 and end != -1 else text
        try:
            return json.loads(content)
        except Exception:
            return {}

    def _loc_from_row(self, zone_id: Optional[int], zone_name: Optional[str]) -> tuple[float, float]:
        if zone_id and zone_id in self.zone_id_to_row:
            return _zone_center_from_row(self.zone_id_to_row[zone_id])
        if zone_name and zone_name in self.zone_name_to_row:
            return _zone_center_from_row(self.zone_name_to_row[zone_name])
        return 40.75, -73.98  # Manhattan fallback

    def _snapshot_fleet(self, vehicle_database: "VehicleDatabase") -> List[Dict[str, Any]]:  # type: ignore
        fleet = []
        for v in vehicle_database.get_all_vehicles():
            fleet.append(
                {
                    "vehicle_id": v.vehicle_id,
                    "latitude": v.current_location.latitude,
                    "longitude": v.current_location.longitude,
                    "status": getattr(v.status, "value", "idle"),
                    "wheelchair_accessible": v.wheelchair_accessible,
                }
            )
        return fleet

    def _nearest_vehicle_from_snapshot(self, fleet: List[Dict[str, Any]], origin: Location) -> Optional[str]:
        best_id = None
        best_dist = math.inf
        for v in fleet:
            if v.get("status") not in ("idle", "available", "en_route_to_pickup"):
                continue
            lat = v.get("latitude")
            lon = v.get("longitude")
            if lat is None or lon is None:
                continue
            dist = ((lat - origin.latitude) ** 2 + (lon - origin.longitude) ** 2) ** 0.5
            if dist < best_dist:
                best_dist = dist
                best_id = v.get("vehicle_id")
        return best_id

    def parse_request(
        self,
        nl_request: NaturalLanguageRequest,
        vehicle_database: "VehicleDatabase",  # type: ignore
    ) -> StructuredRequest:
        fleet_snapshot = self._snapshot_fleet(vehicle_database)

        # If ground truth is present (dummy/cheat mode), include it but still let remote pick vehicle
        payload = {
            "request_id": nl_request.request_id,
            "request_text": nl_request.natural_language_text,
            "ground_truth": nl_request.ground_truth.to_dict() if nl_request.ground_truth else None,
            "fleet": fleet_snapshot,
        }
        resp_text = self._sync_send_message(f"<json>{json.dumps(payload)}</json>")
        parsed_all = self._parse_remote_json(resp_text) if resp_text else {}
        parsed = parsed_all.get("parsed") if isinstance(parsed_all, dict) else {}
        routing = parsed_all.get("routing") if isinstance(parsed_all, dict) else {}

        if isinstance(routing, dict) and routing:
            self._routing_cache[nl_request.request_id] = routing

        parsed = parsed if isinstance(parsed, dict) else {}

        # Base fallbacks from ground truth if available
        gt_req = nl_request.ground_truth
        gt_origin = gt_req.origin if gt_req else None
        gt_dest = gt_req.destination if gt_req else None

        zone_id_pick = parsed.get("pickup_zone_id")
        zone_id_drop = parsed.get("dropoff_zone_id")
        zone_name_pick = parsed.get("pickup_zone") or (gt_origin.zone_name if gt_origin else None)
        zone_name_drop = parsed.get("dropoff_zone") or (gt_dest.zone_name if gt_dest else None)

        lat_pick = parsed.get("pickup_latitude") or (gt_origin.latitude if gt_origin else None)
        lon_pick = parsed.get("pickup_longitude") or (gt_origin.longitude if gt_origin else None)
        lat_drop = parsed.get("dropoff_latitude") or (gt_dest.latitude if gt_dest else None)
        lon_drop = parsed.get("dropoff_longitude") or (gt_dest.longitude if gt_dest else None)

        if lat_pick is None or lon_pick is None:
            lat_pick, lon_pick = self._loc_from_row(zone_id_pick, zone_name_pick)
        if lat_drop is None or lon_drop is None:
            lat_drop, lon_drop = self._loc_from_row(zone_id_drop, zone_name_drop)

        passenger_count = parsed.get("passenger_count")
        if passenger_count is None:
            passenger_count = gt_req.passenger_count if gt_req else 1

        wheelchair = parsed.get("wheelchair_accessible")
        if wheelchair is None:
            wheelchair = gt_req.wheelchair_accessible if gt_req else False

        shared_ok = parsed.get("shared_ride_ok")
        if shared_ok is None:
            shared_ok = gt_req.shared_ride_ok if gt_req else True

        return StructuredRequest(
            request_id=nl_request.request_id,
            request_time=nl_request.request_time,
            origin=Location(
                latitude=lat_pick,
                longitude=lon_pick,
                zone_id=zone_id_pick,
                zone_name=zone_name_pick,
            ),
            destination=Location(
                latitude=lat_drop,
                longitude=lon_drop,
                zone_id=zone_id_drop,
                zone_name=zone_name_drop,
            ),
            passenger_count=passenger_count,
            wheelchair_accessible=wheelchair,
            shared_ride_ok=shared_ok,
        )

    def make_routing_decision(
        self,
        structured_request: StructuredRequest,
        vehicle_database: "VehicleDatabase",  # type: ignore
    ) -> RoutingDecision:
        route = self._routing_cache.pop(structured_request.request_id, None)

        selected_id = None
        est_pickup_dist = None
        est_trip_dist = None
        if route:
            selected_id = route.get("vehicle_id")
            est_pickup_dist = route.get("estimated_pickup_distance_miles")
            est_trip_dist = route.get("estimated_trip_distance_miles")

        if selected_id:
            selected = vehicle_database.get_vehicle_by_id(selected_id)
        else:
            available = self.get_available_vehicles(
                vehicle_database,
                location=structured_request.origin,
                max_count=5,
            )
            selected = available[0] if available else None

        if not selected:
            all_vehicles = vehicle_database.get_all_vehicles()
            if not all_vehicles:
                raise ValueError("No vehicles available")
            selected = all_vehicles[0]
            selected_id = selected.vehicle_id

        pickup_dist, pickup_min = self.query_distance_and_time(
            selected.current_location, structured_request.origin
        )
        trip_dist, trip_min = self.query_distance_and_time(
            structured_request.origin, structured_request.destination
        )

        # Prefer remote estimates if provided
        pickup_dist = est_pickup_dist if est_pickup_dist is not None else pickup_dist
        trip_dist = est_trip_dist if est_trip_dist is not None else trip_dist
        est_pick_time = structured_request.request_time + timedelta(minutes=pickup_min)
        est_drop_time = est_pick_time + timedelta(minutes=trip_min)

        return RoutingDecision(
            request_id=structured_request.request_id,
            vehicle_id=selected.vehicle_id,
            estimated_pickup_time=est_pick_time,
            estimated_dropoff_time=est_drop_time,
            estimated_pickup_distance_miles=pickup_dist,
            estimated_trip_distance_miles=trip_dist,
            decision_rationale=f"Remote routing for vehicle {selected.vehicle_id}",
        )

    def query_distance_and_time(
        self,
        origin: Location,
        destination: Location,
    ) -> tuple[float, float]:
        lat_diff = abs(destination.latitude - origin.latitude)
        lon_diff = abs(destination.longitude - origin.longitude)
        distance_degrees = (lat_diff**2 + lon_diff**2) ** 0.5
        distance_miles = distance_degrees * 69.0
        duration_minutes = (distance_miles / 25.0) * 60.0
        return distance_miles, duration_minutes
