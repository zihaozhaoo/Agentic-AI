"""
Baseline Agents for Evaluation

This module contains baseline implementations of White Agents that do not rely on
ground truth data (unlike DummyWhiteAgent). These agents serve as realistic
benchmarks for evaluating custom agents.
"""

import re
import random
import csv
import os
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from .base_agent import WhiteAgentBase
from .data_structures import (
    NaturalLanguageRequest,
    StructuredRequest,
    RoutingDecision,
    Location,
    RequestPriority
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
        
    def parse_request(
        self,
        nl_request: NaturalLanguageRequest,
        vehicle_database: 'VehicleDatabase'
    ) -> StructuredRequest:
        """
        Returns a request with placeholder locations.
        """
        # Randomly decide if we "parsed" it or not (to simulate noise)
        # But for a baseline, maybe just return a valid but empty request is better
        # to ensure the pipeline keeps moving.
        
        return StructuredRequest(
            request_id=nl_request.request_id,
            request_time=nl_request.request_time,
            origin=Location(latitude=40.75, longitude=-73.98), # Rough center of NYC
            destination=Location(latitude=40.75, longitude=-73.98),
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


class RegexBaselineAgent(WhiteAgentBase):
    """
    A baseline agent that uses simple regex and keyword matching.
    
    This agent attempts to extract:
    - Origin/Destination based on "from" and "to" keywords
    - Zone names based on a loaded dictionary of NYC taxi zones
    """
    
    def __init__(self, agent_name: str = "RegexBaseline", config: Optional[Dict[str, Any]] = None):
        super().__init__(agent_name, config)
        self.zone_lookup = self._load_zones()
        self.zones = list(self.zone_lookup.keys())
        
    def _load_zones(self) -> Dict[str, int]:
        """Load taxi zones from the CSV file in the root directory."""
        zones = {}
        # Assuming the agent is running from the root or we can find the file
        # We'll try a few common paths
        possible_paths = [
            "taxi_zone_lookup.csv",
            "../taxi_zone_lookup.csv",
            "/Users/zhaozihao/Desktop/Agentic-AI/taxi_zone_lookup.csv" # Absolute path fallback
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                try:
                    with open(path, 'r') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            if 'Zone' in row and 'LocationID' in row:
                                zones[row['Zone']] = int(row['LocationID'])
                    break
                except Exception as e:
                    print(f"Error loading zones from {path}: {e}")
                    
        return zones

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
        # We use 0.0, 0.0 as lat/long but provide the zone name and ID
        origin_id = self.zone_lookup.get(origin_zone) if origin_zone else None
        dest_id = self.zone_lookup.get(dest_zone) if dest_zone else None
        
        origin_loc = Location(latitude=40.75, longitude=-73.98, zone_name=origin_zone, zone_id=origin_id)
        dest_loc = Location(latitude=40.75, longitude=-73.98, zone_name=dest_zone, zone_id=dest_id)
        
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
