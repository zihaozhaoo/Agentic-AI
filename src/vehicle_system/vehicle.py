"""
Vehicle Class

Represents a single vehicle in the ride-hailing system.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum


class VehicleStatus(Enum):
    """Current status of a vehicle."""
    IDLE = "idle"  # Available for new requests
    EN_ROUTE_TO_PICKUP = "en_route_to_pickup"  # Driving to pick up passenger
    ON_TRIP = "on_trip"  # Currently serving a passenger
    OFFLINE = "offline"  # Not available


@dataclass
class Vehicle:
    """
    Represents a vehicle in the ride-hailing fleet.

    Attributes:
        vehicle_id: Unique identifier for the vehicle
        current_location: Current geographic location
        status: Current operational status
        wheelchair_accessible: Whether vehicle can accommodate wheelchairs
        capacity: Maximum passenger capacity
        current_passenger_count: Number of passengers currently in vehicle
        assigned_request_id: ID of request currently assigned (if any)
        trip_history: List of completed trip IDs
        total_miles_driven: Total miles driven (all time)
        total_deadhead_miles: Total empty miles driven (all time)
        last_updated: Timestamp of last status update
    """
    vehicle_id: str
    current_location: 'Location'  # Forward reference
    status: VehicleStatus = VehicleStatus.IDLE
    wheelchair_accessible: bool = False
    capacity: int = 4
    current_passenger_count: int = 0

    # Assignment tracking
    assigned_request_id: Optional[str] = None
    destination_location: Optional['Location'] = None  # Where vehicle is heading
    estimated_arrival_time: Optional[datetime] = None

    # Trip history
    trip_history: List[str] = field(default_factory=list)
    total_miles_driven: float = 0.0
    total_deadhead_miles: float = 0.0
    total_revenue: float = 0.0

    # Timestamps
    last_updated: Optional[datetime] = None

    @property
    def is_available(self) -> bool:
        """Check if vehicle is available for new assignments."""
        return self.status == VehicleStatus.IDLE and self.current_passenger_count == 0

    @property
    def has_capacity(self) -> bool:
        """Check if vehicle has capacity for more passengers (for ride-sharing)."""
        return self.current_passenger_count < self.capacity

    def assign_request(
        self,
        request_id: str,
        destination: 'Location',
        estimated_arrival: datetime
    ):
        """
        Assign a request to this vehicle.

        Args:
            request_id: Request ID to assign
            destination: Destination location
            estimated_arrival: Estimated arrival time
        """
        self.assigned_request_id = request_id
        self.destination_location = destination
        self.estimated_arrival_time = estimated_arrival
        self.status = VehicleStatus.EN_ROUTE_TO_PICKUP

    def start_trip(self, request_id: str):
        """
        Start serving a trip (passenger picked up).

        Args:
            request_id: Request ID being served
        """
        self.status = VehicleStatus.ON_TRIP
        self.current_passenger_count += 1

    def complete_trip(
        self,
        request_id: str,
        miles_driven: float,
        revenue: float
    ):
        """
        Complete a trip.

        Args:
            request_id: Request ID that was completed
            miles_driven: Miles driven for this trip
            revenue: Revenue earned from this trip
        """
        self.trip_history.append(request_id)
        self.total_miles_driven += miles_driven
        self.total_revenue += revenue
        self.current_passenger_count = max(0, self.current_passenger_count - 1)

        if self.current_passenger_count == 0:
            self.status = VehicleStatus.IDLE
            self.assigned_request_id = None
            self.destination_location = None
            self.estimated_arrival_time = None

    def add_deadhead_miles(self, miles: float):
        """
        Add deadhead (empty) miles to the vehicle.

        Args:
            miles: Miles driven while empty
        """
        self.total_deadhead_miles += miles
        self.total_miles_driven += miles

    def update_location(self, new_location: 'Location', timestamp: datetime):
        """
        Update vehicle location.

        Args:
            new_location: New location
            timestamp: Update timestamp
        """
        self.current_location = new_location
        self.last_updated = timestamp

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'vehicle_id': self.vehicle_id,
            'current_location': {
                'latitude': self.current_location.latitude,
                'longitude': self.current_location.longitude,
                'zone_id': self.current_location.zone_id,
                'zone_name': self.current_location.zone_name,
            },
            'status': self.status.value,
            'wheelchair_accessible': self.wheelchair_accessible,
            'capacity': self.capacity,
            'current_passenger_count': self.current_passenger_count,
            'assigned_request_id': self.assigned_request_id,
            'is_available': self.is_available,
            'trip_count': len(self.trip_history),
            'total_miles_driven': self.total_miles_driven,
            'total_deadhead_miles': self.total_deadhead_miles,
            'total_revenue': self.total_revenue,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None,
        }

    def __repr__(self) -> str:
        return (f"Vehicle(id={self.vehicle_id}, status={self.status.value}, "
                f"location=({self.current_location.latitude:.4f}, "
                f"{self.current_location.longitude:.4f}), "
                f"available={self.is_available})")
