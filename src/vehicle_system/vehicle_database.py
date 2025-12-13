"""
Vehicle Database

Manages the fleet of vehicles and provides query capabilities.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
import random
import math

from vehicle_system.vehicle import Vehicle, VehicleStatus
from white_agent.data_structures import Location


class VehicleDatabase:
    """
    Database for managing vehicle fleet.

    Maintains real-time locations and availability of all vehicles.
    Provides query interface for white agents.
    """

    def __init__(self):
        """Initialize empty vehicle database."""
        self.vehicles: Dict[str, Vehicle] = {}
        self._spatial_index = None  # Placeholder for spatial indexing

    def add_vehicle(self, vehicle: Vehicle):
        """
        Add a vehicle to the database.

        Args:
            vehicle: Vehicle to add
        """
        self.vehicles[vehicle.vehicle_id] = vehicle

    def remove_vehicle(self, vehicle_id: str):
        """
        Remove a vehicle from the database.

        Args:
            vehicle_id: Vehicle ID to remove
        """
        if vehicle_id in self.vehicles:
            del self.vehicles[vehicle_id]

    def get_vehicle_by_id(self, vehicle_id: str) -> Optional[Vehicle]:
        """
        Get a specific vehicle by ID.

        Args:
            vehicle_id: Vehicle ID

        Returns:
            Vehicle object or None if not found
        """
        return self.vehicles.get(vehicle_id)

    def get_all_vehicles(self) -> List[Vehicle]:
        """
        Get all vehicles in the database.

        Returns:
            List of all vehicles
        """
        return list(self.vehicles.values())

    def get_available_vehicles(
        self,
        location: Optional[Location] = None,
        radius_miles: Optional[float] = None,
        max_count: Optional[int] = None,
        wheelchair_required: bool = False
    ) -> List[Vehicle]:
        """
        Query available vehicles.

        Args:
            location: Center location for proximity search
            radius_miles: Search radius in miles
            max_count: Maximum number of vehicles to return
            wheelchair_required: Filter for wheelchair accessible vehicles

        Returns:
            List of available vehicles, sorted by distance if location provided
        """
        # Filter available vehicles
        available = [
            v for v in self.vehicles.values()
            if v.is_available and (not wheelchair_required or v.wheelchair_accessible)
        ]

        # If location specified, filter by radius and sort by distance
        if location and radius_miles:
            vehicles_with_distance = []
            for vehicle in available:
                distance = self._calculate_distance(
                    location.latitude, location.longitude,
                    vehicle.current_location.latitude, vehicle.current_location.longitude
                )
                if distance <= radius_miles:
                    vehicles_with_distance.append((vehicle, distance))

            # Sort by distance
            vehicles_with_distance.sort(key=lambda x: x[1])
            available = [v for v, _ in vehicles_with_distance]

        elif location:
            # Sort by distance even if no radius specified
            vehicles_with_distance = [
                (v, self._calculate_distance(
                    location.latitude, location.longitude,
                    v.current_location.latitude, v.current_location.longitude
                ))
                for v in available
            ]
            vehicles_with_distance.sort(key=lambda x: x[1])
            available = [v for v, _ in vehicles_with_distance]

        # Limit count
        if max_count:
            available = available[:max_count]

        return available

    def get_vehicles_by_status(self, status: VehicleStatus) -> List[Vehicle]:
        """
        Get all vehicles with a specific status.

        Args:
            status: Vehicle status to filter by

        Returns:
            List of vehicles with the specified status
        """
        return [v for v in self.vehicles.values() if v.status == status]

    def update_vehicle_location(
        self,
        vehicle_id: str,
        new_location: Location,
        timestamp: datetime
    ):
        """
        Update a vehicle's location.

        Args:
            vehicle_id: Vehicle ID
            new_location: New location
            timestamp: Update timestamp
        """
        vehicle = self.get_vehicle_by_id(vehicle_id)
        if vehicle:
            vehicle.update_location(new_location, timestamp)

    def get_fleet_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the fleet.

        Returns:
            Dictionary with fleet statistics
        """
        total = len(self.vehicles)
        if total == 0:
            return {
                'total_vehicles': 0,
                'available_vehicles': 0,
                'busy_vehicles': 0,
                'offline_vehicles': 0,
            }

        status_counts = {}
        for vehicle in self.vehicles.values():
            status = vehicle.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

        total_miles = sum(v.total_miles_driven for v in self.vehicles.values())
        total_deadhead = sum(v.total_deadhead_miles for v in self.vehicles.values())
        total_revenue = sum(v.total_revenue for v in self.vehicles.values())

        return {
            'total_vehicles': total,
            'available_vehicles': status_counts.get('idle', 0),
            'en_route_vehicles': status_counts.get('en_route_to_pickup', 0),
            'on_trip_vehicles': status_counts.get('on_trip', 0),
            'offline_vehicles': status_counts.get('offline', 0),
            'total_miles_driven': total_miles,
            'total_deadhead_miles': total_deadhead,
            'total_revenue': total_revenue,
            'deadhead_ratio': total_deadhead / total_miles if total_miles > 0 else 0,
        }

    def initialize_fleet(
        self,
        num_vehicles: int,
        zone_distribution: Optional[Dict[int, float]] = None,
        taxi_zone_lookup: Optional[Any] = None,
        wheelchair_accessible_ratio: float = 0.1,
        initial_locations: Optional[List[Location]] = None
    ):
        """
        Initialize the vehicle fleet with random locations.

        Args:
            num_vehicles: Number of vehicles to create
            zone_distribution: Distribution of vehicles across zones (zone_id -> weight)
            taxi_zone_lookup: DataFrame with taxi zone information
            wheelchair_accessible_ratio: Ratio of wheelchair accessible vehicles
            initial_locations: Optional list of actual locations to sample from (recommended)
        """
        self.vehicles.clear()

        for i in range(num_vehicles):
            vehicle_id = f"V{i:06d}"

            # Determine location
            if initial_locations and len(initial_locations) > 0:
                # Best option: round-robin through provided locations to avoid clustering
                base = initial_locations[i % len(initial_locations)]
                # Create a fresh Location with tiny jitter so vehicles do not overlap exactly
                location = Location(
                    latitude=base.latitude + random.uniform(-0.0008, 0.0008),
                    longitude=base.longitude + random.uniform(-0.0008, 0.0008),
                    zone_id=base.zone_id,
                    zone_name=base.zone_name
                )
            elif zone_distribution and taxi_zone_lookup is not None:
                # Sample zone based on distribution
                zone_id = self._sample_zone_from_distribution(zone_distribution)
                location = self._get_random_location_in_zone(zone_id, taxi_zone_lookup)
            else:
                # Fallback: random location in NYC area
                # NYC approximate bounds: 40.5-40.9 N, -74.05 to -73.75 W
                location = Location(
                    latitude=random.uniform(40.5, 40.9),
                    longitude=random.uniform(-74.05, -73.75)
                )

            # Determine wheelchair accessibility
            wheelchair_accessible = random.random() < wheelchair_accessible_ratio

            vehicle = Vehicle(
                vehicle_id=vehicle_id,
                current_location=location,
                status=VehicleStatus.IDLE,
                wheelchair_accessible=wheelchair_accessible,
                last_updated=datetime.now()
            )

            self.add_vehicle(vehicle)

    def _sample_zone_from_distribution(self, zone_distribution: Dict[int, float]) -> int:
        """Sample a zone ID based on distribution weights."""
        zones = list(zone_distribution.keys())
        weights = list(zone_distribution.values())
        return random.choices(zones, weights=weights)[0]

    def _get_random_location_in_zone(
        self,
        zone_id: int,
        taxi_zone_lookup: Any
    ) -> Location:
        """
        Get a random location within a taxi zone.

        Args:
            zone_id: Taxi zone ID
            taxi_zone_lookup: DataFrame with taxi zone information

        Returns:
            Random location in the zone
        """
        # Placeholder: use zone center with random offset
        # For actual implementation, use zone boundaries from shapefile
        zone_info = taxi_zone_lookup[taxi_zone_lookup['LocationID'] == zone_id]

        if len(zone_info) == 0:
            # Default to NYC center
            return Location(latitude=40.7128, longitude=-74.0060, zone_id=zone_id)

        # Simple random offset (should use actual zone boundaries)
        base_lat = 40.7128  # NYC center
        base_lon = -74.0060

        return Location(
            latitude=base_lat + random.uniform(-0.05, 0.05),
            longitude=base_lon + random.uniform(-0.05, 0.05),
            zone_id=zone_id,
            zone_name=zone_info.iloc[0].get('Zone', 'Unknown') if len(zone_info) > 0 else 'Unknown'
        )

    def _calculate_distance(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float
    ) -> float:
        """
        Calculate Haversine distance between two points.

        Args:
            lat1, lon1: First point coordinates
            lat2, lon2: Second point coordinates

        Returns:
            Distance in miles
        """
        # Haversine formula
        R = 3959.0  # Earth radius in miles

        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)

        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
        c = 2 * math.asin(math.sqrt(a))

        return R * c

    def __len__(self) -> int:
        """Return number of vehicles in database."""
        return len(self.vehicles)

    def __repr__(self) -> str:
        stats = self.get_fleet_statistics()
        return (f"VehicleDatabase(total={stats['total_vehicles']}, "
                f"available={stats['available_vehicles']}, "
                f"busy={stats.get('on_trip_vehicles', 0)})")
