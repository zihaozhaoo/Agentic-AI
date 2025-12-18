"""
Example: Custom White Agent Implementation

This example shows how to implement a custom white agent that inherits
from WhiteAgentBase and implements the required methods.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from typing import Optional
from white_agent import WhiteAgentBase, NaturalLanguageRequest, StructuredRequest, RoutingDecision, Location
from vehicle_system import VehicleDatabase


class MyCustomWhiteAgent(WhiteAgentBase):
    """
    Example custom white agent implementation.

    This agent demonstrates how to:
    1. Parse natural language requests
    2. Make routing decisions
    3. Query vehicle database
    4. Calculate distances
    """

    def __init__(self, agent_name: str = "MyCustomAgent", config: Optional[dict] = None):
        super().__init__(agent_name, config)

        # Add any custom initialization here
        self.request_count = 0

    def parse_request(
        self,
        nl_request: NaturalLanguageRequest,
        vehicle_database: VehicleDatabase
    ) -> StructuredRequest:
        """
        Parse natural language request into structured format.

        TODO: Implement your parsing logic here!

        You should:
        1. Use NLP/LLM to extract information from nl_request.natural_language_text
        2. Extract origin, destination, time constraints, special requirements
        3. Handle ambiguity and missing information
        4. Return a complete StructuredRequest

        For this example, we'll use ground truth (cheating for demo purposes).
        """
        self.request_count += 1

        # In actual implementation, parse nl_request.natural_language_text
        # For example, using:
        # - Regular expressions for structured patterns
        # - NER (Named Entity Recognition) for locations
        # - LLM APIs (GPT, Claude) for complex parsing
        # - Geocoding APIs for address resolution

        # Demo: use ground truth (replace with actual parsing)
        if nl_request.ground_truth:
            return nl_request.ground_truth
        else:
            # Minimal fallback
            return StructuredRequest(
                request_id=nl_request.request_id,
                request_time=nl_request.request_time,
                origin=Location(latitude=40.7128, longitude=-74.0060),  # Default NYC
                destination=Location(latitude=40.7589, longitude=-73.9851),  # Default Times Square
            )

    def make_routing_decision(
        self,
        structured_request: StructuredRequest,
        vehicle_database: VehicleDatabase
    ) -> RoutingDecision:
        """
        Make routing decision for the request.

        TODO: Implement your routing algorithm here!

        You should:
        1. Query available vehicles near origin
        2. Consider vehicle constraints (wheelchair accessibility, capacity)
        3. Optimize for system-level efficiency (minimize deadhead, maximize revenue)
        4. Handle edge cases (no available vehicles, time constraints)
        5. Return a RoutingDecision with vehicle assignment

        This example implements a simple nearest-vehicle strategy.
        """

        # Strategy 1: Find nearest available vehicle
        available_vehicles = self.get_available_vehicles(
            vehicle_database,
            location=structured_request.origin,
            radius_miles=20.0,  # Search within 20 miles
            max_count=10  # Consider top 10 nearest vehicles
        )

        # Filter by special requirements
        if structured_request.wheelchair_accessible:
            available_vehicles = [v for v in available_vehicles if v.wheelchair_accessible]

        if not available_vehicles:
            # Fallback: use any vehicle
            all_vehicles = vehicle_database.get_all_vehicles()
            if not all_vehicles:
                raise ValueError("No vehicles available in database")
            selected_vehicle = all_vehicles[0]
        else:
            # Select nearest vehicle (they're already sorted by distance)
            selected_vehicle = available_vehicles[0]

        # Calculate distances and times
        pickup_distance, pickup_time = self.query_distance_and_time(
            selected_vehicle.current_location,
            structured_request.origin
        )

        trip_distance, trip_time = self.query_distance_and_time(
            structured_request.origin,
            structured_request.destination
        )

        # Create routing decision
        estimated_pickup_time = structured_request.request_time
        from datetime import timedelta
        estimated_dropoff_time = estimated_pickup_time + timedelta(minutes=pickup_time + trip_time)

        return RoutingDecision(
            request_id=structured_request.request_id,
            vehicle_id=selected_vehicle.vehicle_id,
            estimated_pickup_time=estimated_pickup_time,
            estimated_dropoff_time=estimated_dropoff_time,
            estimated_pickup_distance_miles=pickup_distance,
            estimated_trip_distance_miles=trip_distance,
            decision_rationale=f"Nearest available vehicle (distance: {pickup_distance:.2f} mi)"
        )

    def query_distance_and_time(
        self,
        origin: Location,
        destination: Location
    ) -> tuple[float, float]:
        """
        Query distance and time between two locations.

        TODO: Implement using Google Maps API or similar!

        For production:
        1. Use Google Maps Distance Matrix API
        2. Or use OSRM (Open Source Routing Machine)
        3. Cache results to minimize API calls

        This example uses simple Euclidean approximation.
        """
        import math

        # Haversine distance
        R = 3959.0  # Earth radius in miles

        lat1 = math.radians(origin.latitude)
        lat2 = math.radians(destination.latitude)
        delta_lat = math.radians(destination.latitude - origin.latitude)
        delta_lon = math.radians(destination.longitude - origin.longitude)

        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2)
        c = 2 * math.asin(math.sqrt(a))

        distance_miles = R * c

        # Estimate time: assume average speed of 25 mph in city
        duration_minutes = (distance_miles / 25.0) * 60.0

        return distance_miles, duration_minutes

    def get_statistics(self) -> dict:
        """Get agent statistics."""
        stats = super().get_statistics()
        stats['requests_processed'] = self.request_count
        return stats


def main():
    """
    Demo: Run the custom white agent on a small sample.
    """
    print("Custom White Agent Execution")
    print("="*80)

    # 1. Initialize Simulator
    from request_simulation import RequestSimulator
    project_root = Path(__file__).parent.parent
    taxi_zone_lookup = str(project_root / "taxi_zone_lookup.csv")
    parquet_file = str(project_root / "fhvhv_tripdata_2025-01.parquet")

    request_simulator = RequestSimulator(
        taxi_zone_lookup_path=taxi_zone_lookup,
        template_ratio=1.0
    )

    # 2. Initialize Environment
    from environment import GreenAgentEnvironment, EventLogger
    import logging
    
    # Create logs directory if it doesn't exist
    log_dir = project_root / "logs"
    log_dir.mkdir(exist_ok=True)
    
    logger = EventLogger(
        log_file_path=str(log_dir / "custom_agent.log"),
        console_level=logging.INFO
    )
    
    environment = GreenAgentEnvironment(
        request_simulator=request_simulator,
        logger=logger
    )

    # 3. Initialize Fleet
    print("Initializing fleet...")
    environment.initialize_vehicles(
        num_vehicles=50,
        sample_parquet_path=parquet_file,
        sample_size=500
    )

    # 4. Generate Requests
    print("Generating requests...")
    requests = environment.generate_requests_from_data(
        parquet_path=parquet_file,
        n_requests=5,
        augment_location=False
    )

    # 5. Create Agent
    print("Initializing MyCustomWhiteAgent...")
    white_agent = MyCustomWhiteAgent(
        agent_name="MyCustomAgent_v1"
    )

    # 6. Run Evaluation
    print("Running evaluation...")
    results = environment.run_evaluation(
        white_agent=white_agent,
        requests=requests,
        verbose=True
    )

    # 7. Show Results
    print("\n" + "="*80)
    print("EVALUATION RESULTS")
    print("="*80)
    summary = results['evaluation_summary']
    print(f"Agent: {results['agent_name']}")
    print(f"Score: {summary['overall_score']:.2f}/100")
    print(f"Parsing Accuracy: {summary['parsing_metrics']['origin_zone_accuracy']*100:.1f}%")
    print(f"Net Revenue: ${summary['routing_metrics']['net_revenue']:.2f}")
    print("\nCheck logs/custom_agent.log for details.")

if __name__ == "__main__":
    main()
