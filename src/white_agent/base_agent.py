"""
White Agent Abstract Base Class

This module defines the interface that all white agents must implement
to participate in the Green Agent evaluation.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime

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

    def __init__(self, agent_name: str, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the white agent.

        Args:
            agent_name: Unique name for this agent
            config: Optional configuration dictionary
        """
        self.agent_name = agent_name
        self.config = config or {}

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

    This agent provides minimal functionality:
    - Copies ground truth for parsing (cheating, for testing only)
    - Assigns nearest available vehicle
    """

    def __init__(self, agent_name: str = "DummyAgent", config: Optional[Dict[str, Any]] = None):
        super().__init__(agent_name, config)

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
                origin=Location(latitude=0.0, longitude=0.0),
                destination=Location(latitude=0.0, longitude=0.0),
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
