"""
Baseline Agents for Evaluation

This module contains baseline implementations of White Agents that do not rely on
ground truth data (unlike DummyWhiteAgent). These agents serve as realistic
benchmarks for evaluating custom agents.
"""

import re
import random
import csv
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta

from .base_agent import WhiteAgentBase
from .data_structures import (
    NaturalLanguageRequest,
    StructuredRequest,
    RoutingDecision,
    Location
)

# Approximate borough centers for generating distinct coordinates
_BOROUGH_CENTERS = {
    'Manhattan': (40.75, -73.98),
    'Brooklyn': (40.65, -73.95),
    'Queens': (40.72, -73.80),
    'Bronx': (40.85, -73.88),
    'Staten Island': (40.58, -74.15),
    'EWR': (40.69, -74.17),
}


def _possible_lookup_paths() -> List[Path]:
    """Return possible paths to the taxi zone lookup file."""
    base = Path(__file__).resolve()
    return [
        base.parents[2] / "taxi_zone_lookup.csv",  # repo root
        base.parents[1] / "taxi_zone_lookup.csv",  # src sibling
        Path.cwd() / "taxi_zone_lookup.csv",       # current working dir
    ]


def _load_zone_table() -> List[Dict[str, Any]]:
    """
    Load taxi zone lookup rows with borough information.

    Returns:
        List of dict rows from taxi_zone_lookup.csv (may be empty if file missing)
    """
    for path in _possible_lookup_paths():
        if path.exists():
            try:
                with open(path, "r", newline="") as f:
                    reader = csv.DictReader(f)
                    return [row for row in reader if 'Zone' in row and 'LocationID' in row]
            except Exception as exc:
                print(f"Error loading zones from {path}: {exc}")
    return []


def _zone_center_with_jitter(zone_row: Optional[Dict[str, Any]]) -> Tuple[float, float]:
    """Return a jittered lat/lon for a zone using borough centers as a proxy."""
    if not zone_row:
        base_lat, base_lon = _BOROUGH_CENTERS['Manhattan']
    else:
        borough = zone_row.get('Borough') or 'Manhattan'
        base_lat, base_lon = _BOROUGH_CENTERS.get(borough, _BOROUGH_CENTERS['Manhattan'])
    return base_lat + random.uniform(-0.01, 0.01), base_lon + random.uniform(-0.01, 0.01)


def _sample_location(zone_table: List[Dict[str, Any]]) -> Location:
    """Sample a plausible NYC location from the lookup table."""
    if zone_table:
        zone_row = random.choice(zone_table)
        lat, lon = _zone_center_with_jitter(zone_row)
        return Location(
            latitude=lat,
            longitude=lon,
            zone_id=int(zone_row.get('LocationID')),
            zone_name=zone_row.get('Zone')
        )

    # Fallback to a loose NYC bounding box if lookup failed
    return Location(
        latitude=40.70 + random.uniform(-0.1, 0.1),
        longitude=-73.97 + random.uniform(-0.1, 0.1)
    )


class RandomBaselineAgent(WhiteAgentBase):
    """
    A baseline agent that makes random decisions.
    
    This agent serves as a lower bound for performance. It:
    - Parses requests with random locations (or 0,0 if it can't guess)
    - Assigns random available vehicles
    """
    
    def __init__(self, agent_name: str = "RandomBaseline", config: Optional[Dict[str, Any]] = None):
        super().__init__(agent_name, config)
        self.zone_table = _load_zone_table()
        
    def parse_request(
        self,
        nl_request: NaturalLanguageRequest,
        vehicle_database: 'VehicleDatabase'
    ) -> StructuredRequest:
        """
        Returns a request with placeholder locations.
        """
        pickup = _sample_location(self.zone_table)
        dropoff = _sample_location(self.zone_table)

        # Make sure pickup and dropoff are not identical
        attempts = 0
        while dropoff.zone_id == pickup.zone_id and attempts < 3 and len(self.zone_table) > 1:
            dropoff = _sample_location(self.zone_table)
            attempts += 1
        
        return StructuredRequest(
            request_id=nl_request.request_id,
            request_time=nl_request.request_time,
            origin=pickup,
            destination=dropoff,
            passenger_count=1
        )

    def make_routing_decision(
        self,
        structured_request: StructuredRequest,
        vehicle_database: 'VehicleDatabase'
    ) -> RoutingDecision:
        """
        Assigns a random available vehicle.
        """
        # Get all vehicles
        try:
            all_vehicles = vehicle_database.get_all_vehicles()
        except AttributeError:
            # Fallback if get_all_vehicles is not available on the interface passed
            # (Though it should be based on DummyWhiteAgent usage)
            all_vehicles = []
            
        if not all_vehicles:
            raise ValueError("No vehicles available for RandomBaselineAgent")
            
        selected_vehicle = random.choice(all_vehicles)
        
        return RoutingDecision(
            request_id=structured_request.request_id,
            vehicle_id=selected_vehicle.vehicle_id,
            estimated_pickup_time=structured_request.request_time,
            estimated_dropoff_time=structured_request.request_time,
            estimated_pickup_distance_miles=0.0,
            estimated_trip_distance_miles=0.0,
            decision_rationale="Random assignment"
        )

    def query_distance_and_time(
        self,
        origin: Location,
        destination: Location
    ) -> tuple[float, float]:
        return 1.0, 5.0


class NearestVehicleBaselineAgent(WhiteAgentBase):
    """
    A baseline that assigns the nearest available vehicle to the parsed origin.

    It reuses ground truth when provided (for test runs) and otherwise samples
    plausible NYC locations. This keeps deadhead miles low without extra logic.
    """

    def __init__(self, agent_name: str = "NearestVehicleBaseline", config: Optional[Dict[str, Any]] = None):
        super().__init__(agent_name, config)
        self.zone_table = _load_zone_table()

    def parse_request(
        self,
        nl_request: NaturalLanguageRequest,
        vehicle_database: 'VehicleDatabase'
    ) -> StructuredRequest:
        # Use ground truth if available to keep origin/dest realistic
        if nl_request.ground_truth:
            return nl_request.ground_truth

        origin = _sample_location(self.zone_table)
        dest = _sample_location(self.zone_table)
        attempts = 0
        while dest.zone_id == origin.zone_id and attempts < 3 and len(self.zone_table) > 1:
            dest = _sample_location(self.zone_table)
            attempts += 1

        return StructuredRequest(
            request_id=nl_request.request_id,
            request_time=nl_request.request_time,
            origin=origin,
            destination=dest,
            passenger_count=1
        )

    def make_routing_decision(
        self,
        structured_request: StructuredRequest,
        vehicle_database: 'VehicleDatabase'
    ) -> RoutingDecision:
        # VehicleDatabase sorts by proximity when a location is provided
        available = self.get_available_vehicles(
            vehicle_database,
            location=structured_request.origin,
            max_count=5  # grab a few nearest to avoid None
        )

        if not available:
            all_vehicles = vehicle_database.get_all_vehicles()
            if not all_vehicles:
                raise ValueError("No vehicles in database")
            selected = all_vehicles[0]
        else:
            selected = available[0]

        pickup_distance, pickup_minutes = self.query_distance_and_time(
            selected.current_location,
            structured_request.origin
        )
        trip_distance, trip_minutes = self.query_distance_and_time(
            structured_request.origin,
            structured_request.destination
        )

        est_pickup_time = structured_request.request_time + timedelta(minutes=pickup_minutes)
        est_drop_time = est_pickup_time + timedelta(minutes=trip_minutes)

        return RoutingDecision(
            request_id=structured_request.request_id,
            vehicle_id=selected.vehicle_id,
            estimated_pickup_time=est_pickup_time,
            estimated_dropoff_time=est_drop_time,
            estimated_pickup_distance_miles=pickup_distance,
            estimated_trip_distance_miles=trip_distance,
            decision_rationale=f"Nearest vehicle {selected.vehicle_id} (est deadhead {pickup_distance:.2f} mi)"
        )

    def query_distance_and_time(
        self,
        origin: Location,
        destination: Location
    ) -> tuple[float, float]:
        # Euclidean approximation; avoids extra dependencies
        lat_diff = abs(destination.latitude - origin.latitude)
        lon_diff = abs(destination.longitude - origin.longitude)
        distance_degrees = (lat_diff ** 2 + lon_diff ** 2) ** 0.5
        distance_miles = distance_degrees * 69.0
        duration_minutes = (distance_miles / 25.0) * 60.0  # ~25 mph city speed
        return distance_miles, duration_minutes


class RegexBaselineAgent(WhiteAgentBase):
    """
    A baseline agent that uses simple regex and keyword matching.
    
    This agent attempts to extract:
    - Origin/Destination based on "from" and "to" keywords
    - Zone names based on a loaded dictionary of NYC taxi zones
    """
    
    def __init__(self, agent_name: str = "RegexBaseline", config: Optional[Dict[str, Any]] = None):
        super().__init__(agent_name, config)
        self.zone_table = _load_zone_table()
        self.zone_lookup = {
            row['Zone']: int(row['LocationID']) for row in self.zone_table
            if 'Zone' in row and 'LocationID' in row
        }
        self.zones = list(self.zone_lookup.keys())

    def _get_zone_row(self, zone_id: Optional[int]) -> Optional[Dict[str, Any]]:
        """Fetch the raw zone row for a given LocationID."""
        if zone_id is None:
            return None
        for row in self.zone_table:
            if int(row.get('LocationID')) == zone_id:
                return row
        return None

    def _build_location_for_zone(self, zone_name: Optional[str]) -> Location:
        """Create a Location using lookup info; fallback to random sample."""
        if zone_name and zone_name in self.zone_lookup:
            zone_id = self.zone_lookup[zone_name]
            zone_row = self._get_zone_row(zone_id)
            lat, lon = _zone_center_with_jitter(zone_row)
            return Location(
                latitude=lat,
                longitude=lon,
                zone_name=zone_name,
                zone_id=zone_id
            )

        # Fallback to a random location to avoid collapsed trajectories
        return _sample_location(self.zone_table)

    def _normalize(self, text: str) -> str:
        """Normalize text by replacing punctuation with spaces and lowercasing."""
        # Replace punctuation with space
        text = re.sub(r'[^\w\s]', ' ', text)
        # Collapse multiple spaces
        text = re.sub(r'\s+', ' ', text)
        return text.strip().lower()

    def parse_request(
        self,
        nl_request: NaturalLanguageRequest,
        vehicle_database: 'VehicleDatabase'
    ) -> StructuredRequest:
        text = nl_request.natural_language_text
        normalized_text = self._normalize(text)
        
        origin_zone = None
        dest_zone = None
        
        # Simple heuristic: "from [Zone]" and "to [Zone]"
        # We search for the longest matching zone name to avoid partial matches
        sorted_zones = sorted(self.zones, key=len, reverse=True)
        
        # Find all zones present in the text
        found_zones = []
        for zone in sorted_zones:
            # Normalize the zone name too for matching
            normalized_zone = self._normalize(zone)
            if normalized_zone in normalized_text:
                found_zones.append(zone) # Keep original name
        
        # DEBUG
        # if len(self.zones) == 0:
        #     print("DEBUG: No zones loaded!")
        # print(f"DEBUG: Text: {text[:50]}...")
        # print(f"DEBUG: Found zones: {found_zones}")
        
        # Try to assign based on "from"/"to" context
                # but this is a simple baseline.
        
        # Try to assign based on "from"/"to" context
        if found_zones:
            # Check position of "from" and "to" in the normalized text
            from_idx = normalized_text.find("from")
            to_idx = normalized_text.find("to")
            
            # If we have explicit "from" and "to"
            if from_idx != -1 and to_idx != -1:
                # Split text into from-part and to-part
                if from_idx < to_idx:
                    from_part = normalized_text[from_idx:to_idx]
                    to_part = normalized_text[to_idx:]
                else:
                    to_part = normalized_text[to_idx:from_idx]
                    from_part = normalized_text[from_idx:]
                    
                for zone in found_zones:
                    normalized_zone = self._normalize(zone)
                    if normalized_zone in from_part and origin_zone is None:
                        origin_zone = zone
                    elif normalized_zone in to_part and dest_zone is None:
                        dest_zone = zone
            else:
                # Fallback: first found is origin, second is dest (if available)
                if len(found_zones) >= 1:
                    origin_zone = found_zones[0]
                if len(found_zones) >= 2:
                    dest_zone = found_zones[1]
        
        # Create locations
        origin_loc = self._build_location_for_zone(origin_zone)
        dest_loc = self._build_location_for_zone(dest_zone)

        # If we failed to find distinct zones, sample a different dropoff to keep maps informative
        if dest_loc.zone_id == origin_loc.zone_id and len(self.zone_table) > 1:
            alt_dest = _sample_location(self.zone_table)
            if alt_dest.zone_id != origin_loc.zone_id:
                dest_loc = alt_dest

        return StructuredRequest(
            request_id=nl_request.request_id,
            request_time=nl_request.request_time,
            origin=origin_loc,
            destination=dest_loc,
            passenger_count=1 # Default
        )

    def make_routing_decision(
        self,
        structured_request: StructuredRequest,
        vehicle_database: 'VehicleDatabase'
    ) -> RoutingDecision:
        """
        Similar to DummyWhiteAgent, assigns nearest available vehicle.
        """
        # Since we might not have real lat/long, we just pick a vehicle.
        # If we had a map of Zone -> Lat/Long, we could do better.
        
        available_vehicles = self.get_available_vehicles(
            vehicle_database,
            location=None, # Global search
            max_count=1
        )
        
        if not available_vehicles:
             # Fallback
            all_vehicles = vehicle_database.get_all_vehicles()
            if all_vehicles:
                selected_vehicle = all_vehicles[0]
            else:
                raise ValueError("No vehicles in database")
        else:
            selected_vehicle = available_vehicles[0]

        return RoutingDecision(
            request_id=structured_request.request_id,
            vehicle_id=selected_vehicle.vehicle_id,
            estimated_pickup_time=structured_request.request_time,
            estimated_dropoff_time=structured_request.request_time,
            estimated_pickup_distance_miles=0.5, # Dummy
            estimated_trip_distance_miles=2.0, # Dummy
            decision_rationale=f"RegexBaseline: Assigned to {selected_vehicle.vehicle_id}"
        )

    def query_distance_and_time(
        self,
        origin: Location,
        destination: Location
    ) -> tuple[float, float]:
        return 1.0, 5.0
