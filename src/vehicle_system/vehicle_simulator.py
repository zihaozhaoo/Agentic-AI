"""
Vehicle Simulator

Simulates vehicle movement and trip execution based on routing decisions.
"""

from typing import Optional, Dict, Any, Callable
from datetime import datetime, timedelta
import math

from vehicle_system.vehicle import Vehicle, VehicleStatus
from vehicle_system.vehicle_database import VehicleDatabase
from white_agent.data_structures import RoutingDecision, Location


class VehicleSimulator:
    """
    Simulates vehicle movements and trip execution.

    This component:
    - Accepts routing decisions from white agents
    - Simulates vehicle movement to pickup locations
    - Simulates trip execution
    - Updates vehicle database in real-time
    """

    def __init__(
        self,
        vehicle_database: VehicleDatabase,
        distance_calculator: Optional[Callable[[Location, Location], tuple[float, float]]] = None,
        base_fare: float = 2.50,
        per_mile_rate: float = 1.75,
        per_minute_rate: float = 0.35
    ):
        """
        Initialize vehicle simulator.

        Args:
            vehicle_database: Vehicle database to update
            distance_calculator: Function to calculate distance/time between locations
            base_fare: Base fare for trips
            per_mile_rate: Rate per mile
            per_minute_rate: Rate per minute
        """
        self.vehicle_database = vehicle_database
        self.distance_calculator = distance_calculator or self._default_distance_calculator
        self.base_fare = base_fare
        self.per_mile_rate = per_mile_rate
        self.per_minute_rate = per_minute_rate

        # Track ongoing trips
        self.active_trips: Dict[str, Dict[str, Any]] = {}

    def execute_routing_decision(
        self,
        routing_decision: RoutingDecision,
        pickup_location: Location,
        dropoff_location: Location,
        current_time: datetime
    ) -> Dict[str, Any]:
        """
        Execute a routing decision by updating vehicle state.

        This simulates the white agent's decision being sent to the vehicle.

        Args:
            routing_decision: Routing decision from white agent
            pickup_location: Pickup location
            dropoff_location: Dropoff location
            current_time: Current simulation time

        Returns:
            Dictionary with execution results
        """
        # Get the vehicle
        vehicle = self.vehicle_database.get_vehicle_by_id(routing_decision.vehicle_id)
        if not vehicle:
            return {
                'success': False,
                'error': f'Vehicle {routing_decision.vehicle_id} not found'
            }

        # Calculate actual pickup distance and time
        pickup_distance, pickup_time = self.distance_calculator(
            vehicle.current_location,
            pickup_location
        )

        # Assign request to vehicle
        estimated_pickup_time = current_time + timedelta(minutes=pickup_time)
        vehicle.assign_request(
            request_id=routing_decision.request_id,
            destination=pickup_location,
            estimated_arrival=estimated_pickup_time
        )

        # Create trip record
        trip_info = {
            'request_id': routing_decision.request_id,
            'vehicle_id': routing_decision.vehicle_id,
            'pickup_location': pickup_location,
            'dropoff_location': dropoff_location,
            'request_time': current_time,
            'estimated_pickup_time': estimated_pickup_time,
            'actual_pickup_distance': pickup_distance,
            'actual_pickup_time': pickup_time,
            'status': 'en_route_to_pickup',
        }

        self.active_trips[routing_decision.request_id] = trip_info

        return {
            'success': True,
            'vehicle_id': routing_decision.vehicle_id,
            'pickup_distance_miles': pickup_distance,
            'pickup_time_minutes': pickup_time,
            'estimated_pickup_time': estimated_pickup_time,
        }

    def simulate_trip_completion(
        self,
        request_id: str,
        completion_time: datetime
    ) -> Optional[Dict[str, Any]]:
        """
        Simulate completion of a trip.

        Args:
            request_id: Request ID
            completion_time: Time when trip completes

        Returns:
            Dictionary with trip completion details, or None if trip not found
        """
        if request_id not in self.active_trips:
            return None

        trip_info = self.active_trips[request_id]
        vehicle = self.vehicle_database.get_vehicle_by_id(trip_info['vehicle_id'])

        if not vehicle:
            return None

        # Calculate trip distance and time
        trip_distance, trip_time = self.distance_calculator(
            trip_info['pickup_location'],
            trip_info['dropoff_location']
        )

        # Calculate pickup deadhead miles
        pickup_distance = trip_info['actual_pickup_distance']

        # Update vehicle location to dropoff
        vehicle.update_location(trip_info['dropoff_location'], completion_time)

        # Add deadhead miles
        vehicle.add_deadhead_miles(pickup_distance)

        # Calculate fare
        fare = self._calculate_fare(trip_distance, trip_time)

        # Complete trip on vehicle
        vehicle.complete_trip(
            request_id=request_id,
            miles_driven=trip_distance,
            revenue=fare
        )

        # Update trip info
        trip_info['status'] = 'completed'
        trip_info['completion_time'] = completion_time
        trip_info['trip_distance'] = trip_distance
        trip_info['trip_time'] = trip_time
        trip_info['fare'] = fare
        trip_info['deadhead_miles'] = pickup_distance

        return trip_info

    def advance_time(
        self,
        current_time: datetime,
        time_delta: timedelta
    ):
        """
        Advance simulation time and update vehicle states.

        This method simulates the passage of time and updates vehicles
        that should reach their destinations.

        Args:
            current_time: Current simulation time
            time_delta: Time to advance
        """
        new_time = current_time + time_delta

        # Check all active trips
        for request_id, trip_info in list(self.active_trips.items()):
            if trip_info['status'] == 'en_route_to_pickup':
                # Check if vehicle reached pickup
                if new_time >= trip_info['estimated_pickup_time']:
                    vehicle = self.vehicle_database.get_vehicle_by_id(trip_info['vehicle_id'])
                    if vehicle:
                        # Start trip
                        vehicle.start_trip(request_id)
                        vehicle.update_location(trip_info['pickup_location'], new_time)
                        trip_info['status'] = 'on_trip'
                        trip_info['actual_pickup_time_timestamp'] = new_time

                        # Calculate dropoff time
                        _, trip_time = self.distance_calculator(
                            trip_info['pickup_location'],
                            trip_info['dropoff_location']
                        )
                        trip_info['estimated_dropoff_time'] = new_time + timedelta(minutes=trip_time)

            elif trip_info['status'] == 'on_trip':
                # Check if trip should be completed
                if new_time >= trip_info.get('estimated_dropoff_time', new_time):
                    self.simulate_trip_completion(request_id, new_time)

    def get_trip_status(self, request_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a trip.

        Args:
            request_id: Request ID

        Returns:
            Trip information dictionary or None if not found
        """
        return self.active_trips.get(request_id)

    def get_active_trips(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all active trips.

        Returns:
            Dictionary of active trips
        """
        return self.active_trips.copy()

    def _calculate_fare(self, distance_miles: float, time_minutes: float) -> float:
        """
        Calculate fare for a trip.

        Args:
            distance_miles: Trip distance in miles
            time_minutes: Trip time in minutes

        Returns:
            Total fare
        """
        return (self.base_fare +
                distance_miles * self.per_mile_rate +
                time_minutes * self.per_minute_rate)

    def _default_distance_calculator(
        self,
        origin: Location,
        destination: Location
    ) -> tuple[float, float]:
        """
        Default distance calculator using Haversine formula.

        Args:
            origin: Origin location
            destination: Destination location

        Returns:
            Tuple of (distance_miles, duration_minutes)
        """
        # Haversine distance
        R = 3959.0  # Earth radius in miles

        lat1 = math.radians(origin.latitude)
        lat2 = math.radians(destination.latitude)
        delta_lat = math.radians(destination.latitude - origin.latitude)
        delta_lon = math.radians(destination.longitude - origin.longitude)

        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2)
        c = 2 * math.asin(math.sqrt(a))

        distance = R * c

        # Assume average speed of 25 mph in city
        duration = (distance / 25.0) * 60.0

        return distance, duration

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get simulation statistics.

        Returns:
            Dictionary with simulation statistics
        """
        completed_trips = [
            t for t in self.active_trips.values()
            if t['status'] == 'completed'
        ]

        total_deadhead = sum(t.get('deadhead_miles', 0) for t in completed_trips)
        total_trip_distance = sum(t.get('trip_distance', 0) for t in completed_trips)
        total_revenue = sum(t.get('fare', 0) for t in completed_trips)

        return {
            'total_requests_processed': len(self.active_trips),
            'completed_trips': len(completed_trips),
            'active_trips': len([t for t in self.active_trips.values() if t['status'] != 'completed']),
            'total_deadhead_miles': total_deadhead,
            'total_trip_miles': total_trip_distance,
            'total_revenue': total_revenue,
            'deadhead_ratio': total_deadhead / (total_deadhead + total_trip_distance) if (total_deadhead + total_trip_distance) > 0 else 0,
        }

    def __repr__(self) -> str:
        stats = self.get_statistics()
        return (f"VehicleSimulator(processed={stats['total_requests_processed']}, "
                f"completed={stats['completed_trips']}, "
                f"active={stats['active_trips']})")
