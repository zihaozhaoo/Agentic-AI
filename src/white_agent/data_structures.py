"""
Data Structures for White Agent Interface

These structures define the input/output contract between the green agent
and white agents under evaluation.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum


class RequestPriority(Enum):
    """Priority level for ride requests."""
    NORMAL = "normal"
    URGENT = "urgent"
    SCHEDULED = "scheduled"


@dataclass
class Location:
    """Represents a geographic location."""
    latitude: float
    longitude: float
    zone_id: Optional[int] = None
    zone_name: Optional[str] = None
    address: Optional[str] = None
    poi_name: Optional[str] = None


@dataclass
class StructuredRequest:
    """
    Structured representation of a ride request.

    This is what the white agent should extract from natural language.
    """
    request_id: str
    request_time: datetime

    # Location information
    origin: Location
    destination: Location

    # Time constraints
    requested_pickup_time: Optional[datetime] = None
    requested_dropoff_time: Optional[datetime] = None
    pickup_time_window_minutes: Optional[float] = None
    dropoff_time_window_minutes: Optional[float] = None
    has_arrival_constraint: bool = False

    # Passenger information
    passenger_count: int = 1

    # Special requirements
    wheelchair_accessible: bool = False
    shared_ride_ok: bool = True
    luggage_count: int = 0

    # Customer information
    customer_id: Optional[str] = None

    # Priority
    priority: RequestPriority = RequestPriority.NORMAL

    # Additional constraints (free-form)
    additional_notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'request_id': self.request_id,
            'request_time': self.request_time.isoformat(),
            'origin': {
                'latitude': self.origin.latitude,
                'longitude': self.origin.longitude,
                'zone_id': self.origin.zone_id,
                'zone_name': self.origin.zone_name,
                'address': self.origin.address,
                'poi_name': self.origin.poi_name,
            },
            'destination': {
                'latitude': self.destination.latitude,
                'longitude': self.destination.longitude,
                'zone_id': self.destination.zone_id,
                'zone_name': self.destination.zone_name,
                'address': self.destination.address,
                'poi_name': self.destination.poi_name,
            },
            'requested_pickup_time': self.requested_pickup_time.isoformat() if self.requested_pickup_time else None,
            'requested_dropoff_time': self.requested_dropoff_time.isoformat() if self.requested_dropoff_time else None,
            'pickup_time_window_minutes': self.pickup_time_window_minutes,
            'dropoff_time_window_minutes': self.dropoff_time_window_minutes,
            'has_arrival_constraint': self.has_arrival_constraint,
            'passenger_count': self.passenger_count,
            'wheelchair_accessible': self.wheelchair_accessible,
            'shared_ride_ok': self.shared_ride_ok,
            'luggage_count': self.luggage_count,
            'customer_id': self.customer_id,
            'priority': self.priority.value,
            'additional_notes': self.additional_notes,
        }


@dataclass
class RoutingDecision:
    """
    Routing decision made by the white agent.

    This specifies which vehicle should serve which request.
    """
    request_id: str
    vehicle_id: str

    # Estimated metrics
    estimated_pickup_time: datetime
    estimated_dropoff_time: datetime
    estimated_pickup_distance_miles: float
    estimated_trip_distance_miles: float

    # Route waypoints (if applicable for multi-stop)
    waypoints: List[Location] = field(default_factory=list)

    # Explanation (optional, for debugging)
    decision_rationale: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'request_id': self.request_id,
            'vehicle_id': self.vehicle_id,
            'estimated_pickup_time': self.estimated_pickup_time.isoformat(),
            'estimated_dropoff_time': self.estimated_dropoff_time.isoformat(),
            'estimated_pickup_distance_miles': self.estimated_pickup_distance_miles,
            'estimated_trip_distance_miles': self.estimated_trip_distance_miles,
            'waypoints': [
                {
                    'latitude': wp.latitude,
                    'longitude': wp.longitude,
                    'zone_id': wp.zone_id,
                    'zone_name': wp.zone_name,
                }
                for wp in self.waypoints
            ],
            'decision_rationale': self.decision_rationale,
        }


@dataclass
class NaturalLanguageRequest:
    """
    Natural language request from the green agent.

    This is what the white agent receives as input.
    """
    request_id: str
    request_time: datetime
    natural_language_text: str

    # Ground truth (hidden from white agent, used for evaluation)
    ground_truth: Optional[StructuredRequest] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API communication."""
        return {
            'request_id': self.request_id,
            'request_time': self.request_time.isoformat(),
            'natural_language_text': self.natural_language_text,
        }
