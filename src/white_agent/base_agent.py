"""
White Agent Abstract Base Class

This module defines the interface that all white agents must implement
to participate in the Green Agent evaluation.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

import os
import math
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

from pydantic import BaseModel, Field
from openai import OpenAI
import googlemaps
import geopandas as gpd
from shapely.geometry import Point

from .data_structures import (
    NaturalLanguageRequest,
    StructuredRequest,
    RoutingDecision,
    Location
)


class WhiteAgentBase(ABC):
    """
    Abstract base class for white agents.

    White agents must implement two core capabilities:
    1. Parse natural language requests into structured format
    2. Make routing decisions to assign vehicles to requests
    """

    def __init__(self, agent_name: str, config: Optional[Dict[str, Any]] = None, customer_db: Optional[Any] = None):
        """
        Initialize the white agent.

        Args:
            agent_name: Unique name for this agent
            config: Optional configuration dictionary
            customer_db: Optional customer profile database for resolving personal locations
        """
        self.agent_name = agent_name
        self.config = config or {}
        self.customer_db = customer_db

    @abstractmethod
    def parse_request(
        self,
        nl_request: NaturalLanguageRequest,
        vehicle_database: 'VehicleDatabase'  # Forward reference
    ) -> StructuredRequest:
        """
        Parse a natural language request into structured format.

        The white agent should extract:
        - Origin and destination (coordinates, zone IDs, addresses)
        - Time constraints (pickup/dropoff times, time windows)
        - Passenger information (count, wheelchair needs, etc.)
        - Special requirements (luggage, shared ride preferences, etc.)

        Args:
            nl_request: Natural language request from user
            vehicle_database: Access to vehicle locations and availability

        Returns:
            StructuredRequest with parsed information

        Notes:
            - The agent can query vehicle_database to understand fleet state
            - The agent should handle ambiguous/incomplete requests gracefully
            - If information is missing, use reasonable defaults
        """
        pass

    @abstractmethod
    def make_routing_decision(
        self,
        structured_request: StructuredRequest,
        vehicle_database: 'VehicleDatabase'
    ) -> RoutingDecision:
        """
        Make a routing decision for the given request.

        The white agent should:
        - Query available vehicles from the database
        - Select the most appropriate vehicle
        - Estimate pickup and trip times/distances
        - Consider ongoing trips and future availability

        Args:
            structured_request: Parsed request information
            vehicle_database: Access to vehicle locations and availability

        Returns:
            RoutingDecision specifying vehicle assignment and estimated metrics

        Notes:
            - The agent should optimize for system-level efficiency
            - Consider minimizing deadhead miles (empty driving)
            - Balance response time with overall fleet utilization
            - Handle cases where no vehicle is immediately available
        """
        pass

    def process_request(
        self,
        nl_request: NaturalLanguageRequest,
        vehicle_database: 'VehicleDatabase'
    ) -> tuple[StructuredRequest, RoutingDecision]:
        """
        Complete request processing pipeline.

        This method combines parsing and routing into one call.

        Args:
            nl_request: Natural language request
            vehicle_database: Vehicle database

        Returns:
            Tuple of (structured_request, routing_decision)
        """
        # Step 1: Parse natural language
        structured_request = self.parse_request(nl_request, vehicle_database)

        # Step 2: Make routing decision
        routing_decision = self.make_routing_decision(structured_request, vehicle_database)

        return structured_request, routing_decision

    @abstractmethod
    def query_distance_and_time(
        self,
        origin: Location,
        destination: Location
    ) -> tuple[float, float]:
        """
        Query travel distance and time between two locations.

        This method provides access to routing/mapping services
        (e.g., Google Maps API) for distance/time estimation.

        Args:
            origin: Starting location
            destination: Ending location

        Returns:
            Tuple of (distance_miles, duration_minutes)

        Notes:
            - The green agent provides API access through this interface
            - Agents should cache results to minimize API calls
            - This is used for estimating pickup distances and trip durations
        """
        pass

    def get_available_vehicles(
        self,
        vehicle_database: 'VehicleDatabase',
        location: Optional[Location] = None,
        radius_miles: Optional[float] = None,
        max_count: Optional[int] = None
    ) -> List['Vehicle']:
        """
        Query available vehicles from the database.

        This is a convenience method that wraps vehicle_database queries.

        Args:
            vehicle_database: Vehicle database to query
            location: Center location for proximity search
            radius_miles: Search radius (if location provided)
            max_count: Maximum number of vehicles to return

        Returns:
            List of available Vehicle objects
        """
        return vehicle_database.get_available_vehicles(
            location=location,
            radius_miles=radius_miles,
            max_count=max_count
        )

    def get_vehicle_by_id(
        self,
        vehicle_database: 'VehicleDatabase',
        vehicle_id: str
    ) -> Optional['Vehicle']:
        """
        Get a specific vehicle by ID.

        Args:
            vehicle_database: Vehicle database
            vehicle_id: Vehicle ID

        Returns:
            Vehicle object or None if not found
        """
        return vehicle_database.get_vehicle_by_id(vehicle_id)

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get agent statistics (optional).

        Returns:
            Dictionary with agent-specific statistics
        """
        return {
            'agent_name': self.agent_name,
            'config': self.config
        }


class DummyWhiteAgent(WhiteAgentBase):
    """
    Dummy implementation of white agent for testing.
    
    WARNING: This agent is for TESTING ONLY. It uses ground truth data which
    is considered "cheating" in actual evaluation.
    
    This agent provides minimal functionality:
    - Copies ground truth for parsing (cheating, for testing only)
    - Assigns nearest available vehicle
    """

    def __init__(self, agent_name: str = "DummyAgent", config: Optional[Dict[str, Any]] = None, customer_db: Optional[Any] = None):
        super().__init__(agent_name, config, customer_db)

    def parse_request(
        self,
        nl_request: NaturalLanguageRequest,
        vehicle_database: 'VehicleDatabase'
    ) -> StructuredRequest:
        """
        Dummy parsing: returns ground truth if available.

        For actual implementation, parse nl_request.natural_language_text.
        """
        if nl_request.ground_truth:
            # Cheating: use ground truth for testing
            return nl_request.ground_truth
        else:
            # Minimal parsing (placeholder)
            return StructuredRequest(
                request_id=nl_request.request_id,
                request_time=nl_request.request_time,
                origin=Location(latitude=40.7580, longitude=-73.9855),
                destination=Location(latitude=40.7580, longitude=-73.9855),
                customer_id=nl_request.customer_id,
            )

    def make_routing_decision(
        self,
        structured_request: StructuredRequest,
        vehicle_database: 'VehicleDatabase'
    ) -> RoutingDecision:
        """
        Dummy routing: assign nearest available vehicle.

        For actual implementation, implement sophisticated routing logic.
        """
        # Get available vehicles near origin
        available_vehicles = self.get_available_vehicles(
            vehicle_database,
            location=structured_request.origin,
            radius_miles=10.0,
            max_count=10
        )

        if not available_vehicles:
            # No vehicles available - assign to first vehicle (dummy behavior)
            all_vehicles = vehicle_database.get_all_vehicles()
            if all_vehicles:
                selected_vehicle = all_vehicles[0]
            else:
                raise ValueError("No vehicles in database")
        else:
            # Select first available vehicle (dummy behavior)
            selected_vehicle = available_vehicles[0]

        # Estimate distances and times (placeholder values)
        distance, duration = self.query_distance_and_time(
            selected_vehicle.current_location,
            structured_request.origin
        )

        trip_distance, trip_duration = self.query_distance_and_time(
            structured_request.origin,
            structured_request.destination
        )

        # Create routing decision
        return RoutingDecision(
            request_id=structured_request.request_id,
            vehicle_id=selected_vehicle.vehicle_id,
            estimated_pickup_time=structured_request.request_time,
            estimated_dropoff_time=structured_request.request_time,
            estimated_pickup_distance_miles=distance,
            estimated_trip_distance_miles=trip_distance,
            decision_rationale=f"Dummy: assigned nearest vehicle {selected_vehicle.vehicle_id}"
        )

    def query_distance_and_time(
        self,
        origin: Location,
        destination: Location
    ) -> tuple[float, float]:
        """
        Dummy distance/time query: returns Euclidean distance approximation.

        For actual implementation, use Google Maps API or similar.
        """
        # Simple Euclidean distance in degrees (very rough approximation)
        lat_diff = abs(destination.latitude - origin.latitude)
        lon_diff = abs(destination.longitude - origin.longitude)
        distance_degrees = (lat_diff ** 2 + lon_diff ** 2) ** 0.5

        # Very rough conversion: 1 degree ≈ 69 miles
        distance_miles = distance_degrees * 69.0

        # Assume average speed of 30 mph
        duration_minutes = (distance_miles / 30.0) * 60.0

        return distance_miles, duration_minutes
class LocationExtraction(BaseModel):
    poi_name: Optional[str] = Field(None, description="Name of the point of interest, e.g., 'Empire State Building'")
    address: Optional[str] = Field(None, description="Street address if mentioned, e.g. '350 5th Ave'")
    zone_name_hint: Optional[str] = Field(None, description="Zone name hint if mentioned, e.g. 'Midtown'")

class RideExtraction(BaseModel):
    pickup: LocationExtraction
    dropoff: LocationExtraction
    passenger_count: int = Field(1, description="Number of passengers")
    wheelchair_accessible: bool = Field(False, description="Whether WAV/wheelchair is requested")
    shared_ride_ok: bool = Field(True, description="Whether the user accepts shared rides")
    has_arrival_constraint: bool = Field(False, description="True if user specified a 'must arrive by' time")
    requested_pickup_time_str: Optional[str] = Field(None, description="Requested pickup time in ISO format")
    requested_dropoff_time_str: Optional[str] = Field(None, description="Requested dropoff/arrival time in ISO format")

class NaturalLanguageAgent(WhiteAgentBase):
    """
    A White Agent that:
    1. Uses OpenAI to extract address/POI text.
    2. Uses Google Maps to Geocode that text into Lat/Lon.
    3. Uses GeoPandas (Shapefile) to map Lat/Lon -> Precise NYC Taxi Zone ID.
    4. Routes the nearest vehicle.
    
    WARNING: Error suppression is removed. This agent will raise exceptions if APIs fail or files are missing.
    """

    def __init__(self, agent_name: str = "NaturalLanguageAgent", config: Optional[Dict[str, Any]] = None, customer_db: Optional[Any] = None):
        super().__init__(agent_name, config, customer_db)

        # 1. Initialize OpenAI Client
        self.openai_client = OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY")
        )

        # 2. Initialize Google Maps Client
        self.gmaps_client = None
        gmaps_key = os.environ.get("GOOGLE_MAPS_API_KEY")
        if gmaps_key:
            self.gmaps_client = googlemaps.Client(key=gmaps_key)
        else:
            # Raise error immediately if key is missing, rather than warning
            raise ValueError("GOOGLE_MAPS_API_KEY environment variable is missing!")

        # 3. Load Shapefile for Zone Lookup
        self.gdf_zones = self._load_shapefile()

    def _load_shapefile(self) -> gpd.GeoDataFrame:
        """
        Loads the NYC Taxi Zones shapefile and reprojects to Lat/Lon (EPSG:4326).
        Raises FileNotFoundError if no file is found.
        """
        candidate_paths = [
            Path("/Users/jiangwolin/Downloads/Agentic-AI 2/taxi_zones/taxi_zones.shp"),
            Path("taxi_zones/taxi_zones.shp"),
            Path(__file__).parent.parent.parent / "taxi_zones" / "taxi_zones.shp",
        ]

        for shp_path in candidate_paths:
            if shp_path.exists():
                logging.info(f"Loading shapefile from {shp_path}...")
                # No try/except here. If the file is corrupt, let gpd.read_file raise the error.
                gdf = gpd.read_file(shp_path)
                
                if gdf.crs != "EPSG:4326":
                    gdf = gdf.to_crs("EPSG:4326")
                
                logging.info(f"Shapefile loaded successfully. {len(gdf)} zones found.")
                return gdf
        
        # If loop finishes, no file was found. Raise explicitly.
        raise FileNotFoundError(f"Could not find 'taxi_zones.shp' in any candidate paths: {[str(p) for p in candidate_paths]}")

    def _get_zone_from_coords(self, lat: float, lon: float) -> Tuple[Optional[int], Optional[str]]:
        """
        Performs a Point-in-Polygon check to find the Zone ID and Name.
        """
        if self.gdf_zones is None:
            raise RuntimeError("Shapefile not loaded, cannot lookup zones.")
            
        if lat == 0.0 or lon == 0.0:
            # Invalid coordinates, cannot lookup
            print("Warning: Coordinates are (0.0, 0.0), skipping zone lookup.")
            return None, None

        point = Point(lon, lat)

        # Filter the GeoDataFrame to find the containing polygon
        match = self.gdf_zones[self.gdf_zones.contains(point)]

        if not match.empty:
            row = match.iloc[0]
            return int(row['LocationID']), row['zone']
        
        # If point is outside all polygons (e.g. in New Jersey or ocean)
        print(f"Warning: Coordinate ({lat}, {lon}) falls outside all NYC Taxi Zones.")
        return None, None

    def _get_customer_context(self, customer_id: Optional[str]) -> str:
        """
        Get customer profile information for LLM context.

        Args:
            customer_id: Customer ID

        Returns:
            Formatted string with customer profile information for LLM prompt
        """
        if not customer_id or not self.customer_db:
            return ""

        profile = self.customer_db.get_profile(customer_id)
        if not profile:
            return ""

        # Format customer profile information
        context_parts = ["\n## Customer Profile Information"]
        context_parts.append(f"Customer ID: {profile.customer_id}")

        # Add home location
        if profile.home:
            context_parts.append(f"- Home: {profile.home.zone_name}, {profile.home.borough} (Zone ID: {profile.home.zone_id})")

        # Add work location
        if profile.work:
            context_parts.append(f"- Work/Office: {profile.work.zone_name}, {profile.work.borough} (Zone ID: {profile.work.zone_id})")

        # Add frequent locations
        if profile.frequent_locations:
            context_parts.append("- Frequent locations:")
            for loc in profile.frequent_locations:
                context_parts.append(f"  * {loc.label}: {loc.zone_name}, {loc.borough} (Zone ID: {loc.zone_id})")

        context_parts.append("\nWhen the user mentions personal locations like 'home', 'my house', 'work', 'office', etc., resolve them to the zone name and borough from this profile.")

        return "\n".join(context_parts)

    def _looks_personal_reference(self, label: str) -> bool:
        label_lower = label.lower()
        personal_tokens = [
            "home",
            "house",
            "place",
            "work",
            "office",
            "gym",
            "parents",
            "mother",
            "father",
            "sister",
            "brother",
            "friend",
        ]
        return any(token in label_lower for token in personal_tokens)

    def _apply_personal_location_fallback(
        self,
        loc_data: LocationExtraction,
        nl_text: str,
        customer_id: Optional[str]
    ) -> None:
        if not customer_id or not self.customer_db:
            return

        if loc_data.address or loc_data.poi_name:
            return

        if loc_data.zone_name_hint and not self._looks_personal_reference(loc_data.zone_name_hint):
            return

        profile = self.customer_db.get_profile(customer_id)
        if not profile:
            return

        candidates = []
        if loc_data.zone_name_hint:
            candidates.append(loc_data.zone_name_hint)
        if nl_text:
            candidates.append(nl_text)

        for text in candidates:
            personal = profile.get_personal_poi_by_label(text)
            if personal:
                loc_data.zone_name_hint = f"{personal.zone_name}, {personal.borough}"
                return

    def _geocode_location(self, loc_data: LocationExtraction) -> Tuple[float, float]:
        """
        Converts extracted text -> (lat, lng) using Google Maps.
        Adds NYC context to ensure accurate geocoding.
        Raises Exceptions on API failure.
        """
        if not self.gmaps_client:
            raise RuntimeError("Google Maps client is not initialized.")

        search_query = loc_data.address or loc_data.poi_name or loc_data.zone_name_hint

        if not search_query:
            print("Warning: No address/POI info to geocode. Falling back to Midtown Manhattan.")
            return 40.7580, -73.9855

        # Always add NYC context to ensure Google Maps searches in New York City
        search_query += ", New York, NY"

        # No try/except here. If network fails or quota exceeded, let it raise.
        results = self.gmaps_client.geocode(search_query)
        
        if results and len(results) > 0:
            location = results[0]['geometry']['location']
            return location['lat'], location['lng']
        else:
            # Explicitly raise if Google returns no results (invalid address)
            raise ValueError(f"Google Maps Geocoding returned 0 results for query: '{search_query}'")

    def parse_request(
        self,
        nl_request: NaturalLanguageRequest,
        vehicle_database: 'VehicleDatabase'
    ) -> StructuredRequest:
        """
        Pipeline: LLM Parse -> Google Maps Geocode -> Shapefile Zone Lookup
        No error suppression.
        """
        nl_text = nl_request.natural_language_text
        current_time_str = nl_request.request_time.isoformat()

        # Get customer context if available
        customer_context = self._get_customer_context(nl_request.customer_id)

        system_prompt = "\n".join([
            f"You are a ride-hailing dispatcher in NYC. Current time: {current_time_str}.",
            "Extract exactly one pickup and one dropoff location from the user's request.",
            "Rules:",
            "- Always fill both pickup and dropoff.",
            "- If the request uses 'to X from Y', pickup is Y and dropoff is X.",
            "- If multiple stops are mentioned, ignore intermediate stops and use the final destination as dropoff.",
            "- Prefer addresses; use zone/neighborhood names with borough context when available; use POIs only when no address/zone is given.",
            "- If a personal reference is mentioned (home/work/office/my place), resolve it using the customer profile and output the profile's zone name + borough.",
            "- Do not invent locations beyond the request or customer profile.",
            "- Assume NYC unless explicitly stated otherwise.",
            "- Resolve relative times (e.g. 'in 10 mins') to absolute ISO timestamps.",
            customer_context,
        ]).strip()

        # 1. Extract Text Data via OpenAI (Let it raise if API fails)
        completion = self.openai_client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": nl_text},
            ],
            response_format=RideExtraction,
        )
        
        # Check if parsing was refused or failed (OpenAI specific checks)
        if not completion.choices or not completion.choices[0].message.parsed:
             raise RuntimeError(f"OpenAI failed to parse structure. Response: {completion}")
             
        extracted = completion.choices[0].message.parsed

        self._apply_personal_location_fallback(extracted.pickup, nl_text, nl_request.customer_id)
        self._apply_personal_location_fallback(extracted.dropoff, nl_text, nl_request.customer_id)

        # 2. Geocode (Get Lat/Lon) - Will raise ValueError if address invalid
        p_lat, p_lon = self._geocode_location(extracted.pickup)
        d_lat, d_lon = self._geocode_location(extracted.dropoff)

        # 3. Geometric Lookup (Get Zone ID from Lat/Lon)
        p_zone_id, p_zone_name = self._get_zone_from_coords(p_lat, p_lon)
        d_zone_id, d_zone_name = self._get_zone_from_coords(d_lat, d_lon)

        # Fallback for name only if spatial lookup returned None (Point outside NYC)
        p_zone_name = p_zone_name or extracted.pickup.zone_name_hint or "Unknown Zone"
        d_zone_name = d_zone_name or extracted.dropoff.zone_name_hint or "Unknown Zone"

        # 4. Parse Times (Simple ISO parsing)
        req_pickup_time = None
        if extracted.requested_pickup_time_str:
            req_pickup_time = datetime.fromisoformat(extracted.requested_pickup_time_str)

        req_dropoff_time = None
        if extracted.requested_dropoff_time_str:
            req_dropoff_time = datetime.fromisoformat(extracted.requested_dropoff_time_str)

        # 5. Return Result
        return StructuredRequest(
            request_id=nl_request.request_id,
            request_time=nl_request.request_time,
            origin=Location(
                latitude=p_lat,
                longitude=p_lon,
                zone_id=p_zone_id,
                zone_name=p_zone_name,
                address=extracted.pickup.address,
                poi_name=extracted.pickup.poi_name
            ),
            destination=Location(
                latitude=d_lat,
                longitude=d_lon,
                zone_id=d_zone_id,
                zone_name=d_zone_name,
                address=extracted.dropoff.address,
                poi_name=extracted.dropoff.poi_name
            ),
            requested_pickup_time=req_pickup_time,
            requested_dropoff_time=req_dropoff_time,
            has_arrival_constraint=extracted.has_arrival_constraint,
            passenger_count=extracted.passenger_count,
            wheelchair_accessible=extracted.wheelchair_accessible,
            shared_ride_ok=extracted.shared_ride_ok,
            customer_id=None
        )

    def make_routing_decision(
        self,
        structured_request: StructuredRequest,
        vehicle_database: 'VehicleDatabase'
    ) -> RoutingDecision:
        """
        Assigns the nearest available vehicle to the geocoded origin.
        """
        available_vehicles = vehicle_database.get_available_vehicles(
            location=structured_request.origin,
            max_count=25,
            wheelchair_required=structured_request.wheelchair_accessible,
        )
        if not available_vehicles:
            raise ValueError("No available vehicles found for routing decision.")

        best_vehicle = available_vehicles[0]

        pickup_dist_miles, pickup_minutes = self.query_distance_and_time(
            best_vehicle.current_location, structured_request.origin
        )
        trip_dist_miles, trip_minutes = self.query_distance_and_time(
            structured_request.origin, structured_request.destination
        )

        est_pickup_time = structured_request.request_time + timedelta(minutes=pickup_minutes)
        est_dropoff_time = est_pickup_time + timedelta(minutes=trip_minutes)

        return RoutingDecision(
            request_id=structured_request.request_id,
            vehicle_id=best_vehicle.vehicle_id,
            estimated_pickup_time=est_pickup_time,
            estimated_dropoff_time=est_dropoff_time,
            estimated_pickup_distance_miles=pickup_dist_miles,
            estimated_trip_distance_miles=trip_dist_miles,
            decision_rationale=(
                f"NaturalLanguageAgent: Assigned vehicle {best_vehicle.vehicle_id} "
                f"in {structured_request.origin.zone_name} ({pickup_dist_miles:.2f} mi)"
            ),
        )

    def query_distance_and_time(self, origin: Location, destination: Location) -> tuple[float, float]:
        """Helper for distance calculation."""
        lat_diff = abs(destination.latitude - origin.latitude)
        lon_diff = abs(destination.longitude - origin.longitude)
        distance_miles = (lat_diff**2 + lon_diff**2)**0.5 * 69.0
        return distance_miles, (distance_miles / 30.0) * 60.0
