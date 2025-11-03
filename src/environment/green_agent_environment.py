"""
Green Agent Environment

Main orchestrator that coordinates all components of the evaluation system.
"""

from typing import Optional, List, Dict, Any, Callable
from datetime import datetime, timedelta
import json
from pathlib import Path
import random
import time

from request_simulation import RequestSimulator
from white_agent import WhiteAgentBase, NaturalLanguageRequest, StructuredRequest, Location
from vehicle_system import VehicleDatabase, VehicleSimulator, Vehicle
from evaluation import Evaluator
from utils import EventLogger


class GreenAgentEnvironment:
    """
    Green Agent Environment - Main evaluation orchestrator.

    This class coordinates:
    1. Request generation (from RequestSimulator)
    2. White agent interaction
    3. Vehicle simulation
    4. Performance evaluation
    """

    def __init__(
        self,
        request_simulator: RequestSimulator,
        evaluator: Optional[Evaluator] = None,
        distance_calculator: Optional[Callable[[Location, Location], tuple[float, float]]] = None,
        logger: Optional[EventLogger] = None
    ):
        """
        Initialize the Green Agent Environment.

        Args:
            request_simulator: Request simulator for generating NL requests
            evaluator: Evaluator for performance measurement (creates default if None)
            distance_calculator: Function to calculate distance/time between locations
            logger: Event logger (creates default if None)
        """
        self.request_simulator = request_simulator
        self.evaluator = evaluator or Evaluator()
        self.distance_calculator = distance_calculator
        self.logger = logger or EventLogger()

        # Initialize vehicle system
        self.vehicle_database = VehicleDatabase()
        self.vehicle_simulator = VehicleSimulator(
            vehicle_database=self.vehicle_database,
            distance_calculator=distance_calculator
        )

        # Simulation state
        self.current_time: Optional[datetime] = None
        self.simulation_start_time: Optional[datetime] = None
        self.simulation_end_time: Optional[datetime] = None

        # Request tracking
        self.processed_requests: List[Dict[str, Any]] = []

    def initialize_vehicles(
        self,
        num_vehicles: int,
        zone_distribution: Optional[Dict[int, float]] = None,
        wheelchair_accessible_ratio: float = 0.1,
        sample_parquet_path: Optional[str] = None,
        sample_size: int = 1000
    ):
        """
        Initialize the vehicle fleet.

        Args:
            num_vehicles: Number of vehicles to create
            zone_distribution: Distribution of vehicles across zones
            wheelchair_accessible_ratio: Ratio of wheelchair accessible vehicles
            sample_parquet_path: Optional path to sample trip data for realistic locations
            sample_size: Number of trips to sample for location distribution
        """
        print(f"Initializing {num_vehicles} vehicles...")

        # Get taxi zone lookup from request simulator
        taxi_zone_lookup = self.request_simulator.preprocessor.zone_lookup

        # Sample initial locations from actual trip data if provided
        initial_locations = None
        if sample_parquet_path:
            print(f"  - Sampling {sample_size} trips for realistic vehicle locations...")
            try:
                import pandas as pd
                df = pd.read_parquet(sample_parquet_path)

                # Sample trips and extract pickup locations
                if len(df) > sample_size:
                    df = df.sample(n=sample_size, random_state=42)

                # Extract unique pickup locations with zone info
                initial_locations = []
                for _, row in df.iterrows():
                    # Try to get coordinates if available
                    lat = row.get('pickup_latitude', None) or row.get('PULatitude', None)
                    lon = row.get('pickup_longitude', None) or row.get('PULongitude', None)
                    zone_id = row.get('PULocationID', None)

                    # If no coordinates, use zone center approximation
                    if lat is None or lon is None:
                        # Use NYC zone center with offset based on zone
                        # Manhattan: 40.75, -73.98
                        # Brooklyn: 40.65, -73.95
                        # Queens: 40.72, -73.80
                        # Bronx: 40.85, -73.88
                        borough_centers = {
                            'Manhattan': (40.75, -73.98),
                            'Brooklyn': (40.65, -73.95),
                            'Queens': (40.72, -73.80),
                            'Bronx': (40.85, -73.88),
                            'Staten Island': (40.58, -74.15),
                        }

                        zone_info = taxi_zone_lookup[taxi_zone_lookup['LocationID'] == zone_id]
                        if len(zone_info) > 0:
                            borough = zone_info.iloc[0].get('Borough', 'Manhattan')
                            center = borough_centers.get(borough, (40.7128, -74.0060))
                            lat = center[0] + random.uniform(-0.02, 0.02)
                            lon = center[1] + random.uniform(-0.02, 0.02)
                        else:
                            lat = 40.7128 + random.uniform(-0.1, 0.1)
                            lon = -74.0060 + random.uniform(-0.1, 0.1)

                    if lat and lon:
                        initial_locations.append(Location(
                            latitude=lat,
                            longitude=lon,
                            zone_id=zone_id
                        ))

                print(f"    ✓ Sampled {len(initial_locations)} unique locations")
            except Exception as e:
                print(f"    ✗ Failed to sample locations: {e}")
                print(f"    ✓ Falling back to zone-based initialization")
                initial_locations = None

        self.vehicle_database.initialize_fleet(
            num_vehicles=num_vehicles,
            zone_distribution=zone_distribution,
            taxi_zone_lookup=taxi_zone_lookup,
            wheelchair_accessible_ratio=wheelchair_accessible_ratio,
            initial_locations=initial_locations
        )

        print(f"  ✓ Initialized {len(self.vehicle_database)} vehicles")
        stats = self.vehicle_database.get_fleet_statistics()
        print(f"  ✓ Available: {stats['available_vehicles']}")
        print(f"  ✓ Wheelchair accessible: {int(num_vehicles * wheelchair_accessible_ratio)}")

    def run_evaluation(
        self,
        white_agent: WhiteAgentBase,
        requests: List[Dict[str, Any]],
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Run complete evaluation of a white agent.

        Args:
            white_agent: White agent to evaluate
            requests: List of request dictionaries from RequestSimulator
            start_time: Simulation start time (uses first request time if None)
            end_time: Simulation end time (uses last request time if None)
            verbose: Whether to print progress

        Returns:
            Dictionary with evaluation results
        """
        if not requests:
            raise ValueError("No requests provided for evaluation")

        # Set simulation time bounds
        self.simulation_start_time = start_time or requests[0]['request_time']
        self.simulation_end_time = end_time or requests[-1]['request_time']
        self.current_time = self.simulation_start_time

        if verbose:
            print("\n" + "="*80)
            print(f"STARTING EVALUATION: {white_agent.agent_name}")
            print("="*80)
            print(f"  Total requests: {len(requests)}")
            print(f"  Start time: {self.simulation_start_time}")
            print(f"  End time: {self.simulation_end_time}")
            print(f"  Fleet size: {len(self.vehicle_database)}")
            print()

        # Log evaluation start
        if self.simulation_start_time:
            self.logger.log_evaluation_start(
                agent_name=white_agent.agent_name,
                num_requests=len(requests),
                num_vehicles=len(self.vehicle_database),
                start_time=self.simulation_start_time
            )

        # Reset evaluator
        self.evaluator.reset()
        self.processed_requests.clear()

        # Process each request
        for i, request_data in enumerate(requests):
            # Convert to NaturalLanguageRequest
            nl_request = self._convert_to_nl_request(request_data)

            # Update simulation time
            self.current_time = nl_request.request_time

            # Log request arrival
            self.logger.log_request_arrival(
                request_id=nl_request.request_id,
                request_time=nl_request.request_time,
                natural_language_text=nl_request.natural_language_text,
                ground_truth=nl_request.ground_truth.to_dict() if nl_request.ground_truth else None
            )

            if verbose and (i + 1) % 50 == 0:
                print(f"  Processing request {i + 1} / {len(requests)}...")

            # Process request through white agent
            try:
                # Time parsing
                parse_start = time.time()
                parsed_request, routing_decision = white_agent.process_request(
                    nl_request,
                    self.vehicle_database
                )
                parse_time = (time.time() - parse_start) * 1000  # ms

                # Log parsing result
                self.logger.log_parsing_result(
                    request_id=nl_request.request_id,
                    parsed_request=parsed_request.to_dict(),
                    parsing_time_ms=parse_time
                )

                # Log routing decision
                available_count = len(self.vehicle_database.get_available_vehicles())
                self.logger.log_routing_decision(
                    request_id=nl_request.request_id,
                    routing_decision=routing_decision.to_dict(),
                    decision_time_ms=parse_time,
                    available_vehicles_count=available_count
                )

                # Log vehicle assignment
                vehicle = self.vehicle_database.get_vehicle_by_id(routing_decision.vehicle_id)
                if vehicle:
                    self.logger.log_vehicle_assignment(
                        vehicle_id=routing_decision.vehicle_id,
                        request_id=nl_request.request_id,
                        current_location={
                            'latitude': vehicle.current_location.latitude,
                            'longitude': vehicle.current_location.longitude
                        },
                        pickup_location={
                            'latitude': parsed_request.origin.latitude,
                            'longitude': parsed_request.origin.longitude
                        },
                        estimated_pickup_distance=routing_decision.estimated_pickup_distance_miles,
                        estimated_pickup_time=(routing_decision.estimated_pickup_time - nl_request.request_time).total_seconds() / 60
                    )

                # Execute routing decision in simulator
                execution_result = self.vehicle_simulator.execute_routing_decision(
                    routing_decision,
                    parsed_request.origin,
                    parsed_request.destination,
                    self.current_time
                )

                # Simulate trip completion (simplified - instant completion for now)
                trip_result = self.vehicle_simulator.simulate_trip_completion(
                    nl_request.request_id,
                    self.current_time + timedelta(minutes=30)  # Placeholder
                )

                # Log trip completion
                if trip_result:
                    self.logger.log_trip_completion(
                        vehicle_id=routing_decision.vehicle_id,
                        request_id=nl_request.request_id,
                        trip_distance=trip_result.get('trip_distance', 0),
                        trip_time=trip_result.get('trip_time', 0),
                        fare=trip_result.get('fare', 0),
                        deadhead_miles=trip_result.get('deadhead_miles', 0)
                    )

                # Evaluate request
                self.evaluator.evaluate_request(
                    nl_request,
                    parsed_request,
                    routing_decision,
                    trip_result
                )

                # Track processed request
                self.processed_requests.append({
                    'request_id': nl_request.request_id,
                    'success': True,
                    'parsed_request': parsed_request.to_dict(),
                    'routing_decision': routing_decision.to_dict(),
                    'execution_result': execution_result,
                    'trip_result': trip_result,
                })

            except Exception as e:
                if verbose:
                    print(f"  ERROR processing request {nl_request.request_id}: {e}")

                # Log error
                self.logger.log_error(
                    error_type='REQUEST_PROCESSING_ERROR',
                    error_message=str(e),
                    context={'request_id': nl_request.request_id}
                )

                self.processed_requests.append({
                    'request_id': nl_request.request_id,
                    'success': False,
                    'error': str(e),
                })

        # Get final evaluation summary
        evaluation_summary = self.evaluator.get_summary()

        # Log evaluation end
        self.logger.log_evaluation_end(
            agent_name=white_agent.agent_name,
            summary=evaluation_summary,
            end_time=datetime.now()
        )

        if verbose:
            print("\n" + "="*80)
            print("EVALUATION COMPLETE")
            print("="*80)
            self._print_summary(evaluation_summary)

        return {
            'agent_name': white_agent.agent_name,
            'evaluation_summary': evaluation_summary,
            'processed_requests': len(self.processed_requests),
            'successful_requests': sum(1 for r in self.processed_requests if r.get('success')),
            'failed_requests': sum(1 for r in self.processed_requests if not r.get('success')),
            'vehicle_stats': self.vehicle_database.get_fleet_statistics(),
            'simulator_stats': self.vehicle_simulator.get_statistics(),
            'logging_stats': self.logger.get_statistics(),
        }

    def generate_requests_from_data(
        self,
        parquet_path: str,
        n_requests: int = 100,
        augment_location: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Generate requests from trip data.

        This is a convenience method that wraps RequestSimulator.

        Args:
            parquet_path: Path to parquet file with trip data
            n_requests: Number of requests to generate
            augment_location: Whether to augment with exact coordinates

        Returns:
            List of request dictionaries
        """
        # Load and preprocess data
        df = self.request_simulator.load_and_preprocess_data(
            parquet_path,
            sample_size=n_requests * 2  # Load extra for filtering
        )

        # Generate customer profiles
        print("Generating customer profiles...")
        self.request_simulator.customer_db.generate_profiles(200)

        # Simulate requests
        requests = self.request_simulator.simulate_requests(
            df,
            n_requests=n_requests,
            augment_location=augment_location
        )

        return requests

    def save_results(
        self,
        results: Dict[str, Any],
        output_path: str
    ):
        """
        Save evaluation results to JSON file.

        Args:
            results: Results dictionary from run_evaluation
            output_path: Output file path
        """
        # Convert datetime objects for JSON serialization
        serializable_results = self._make_serializable(results)

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w') as f:
            json.dump(serializable_results, f, indent=2)

        print(f"\nResults saved to {output_path}")

    def _get_zone_center(self, zone_id: int, zone_name: str = None) -> tuple[float, float]:
        """
        Get approximate center coordinates for a taxi zone.

        Args:
            zone_id: Taxi zone ID
            zone_name: Optional zone name for fallback

        Returns:
            (latitude, longitude) tuple
        """
        # Borough-based zone centers (approximate)
        borough_centers = {
            'Manhattan': (40.7589, -73.9851),
            'Brooklyn': (40.6782, -73.9442),
            'Queens': (40.7282, -73.7949),
            'Bronx': (40.8448, -73.8648),
            'Staten Island': (40.5795, -74.1502),
            'EWR': (40.6895, -74.1745),  # Newark Airport
        }

        # Try to get borough from zone lookup
        try:
            zone_lookup = self.request_simulator.preprocessor.zone_lookup
            zone_info = zone_lookup[zone_lookup['LocationID'] == zone_id]

            if len(zone_info) > 0:
                borough = zone_info.iloc[0].get('Borough', 'Unknown')
                if borough in borough_centers:
                    center = borough_centers[borough]
                    # Add small random offset to spread vehicles
                    lat = center[0] + random.uniform(-0.01, 0.01)
                    lon = center[1] + random.uniform(-0.01, 0.01)
                    return lat, lon
        except Exception as e:
            self.logger.log_error(
                error_type='ZONE_CENTER_LOOKUP_ERROR',
                error_message=str(e),
                context={'zone_id': zone_id}
            )

        # Default: NYC center (Times Square area)
        return 40.7589 + random.uniform(-0.01, 0.01), -73.9851 + random.uniform(-0.01, 0.01)

    def _convert_to_nl_request(self, request_data: Dict[str, Any]) -> NaturalLanguageRequest:
        """
        Convert request data from RequestSimulator to NaturalLanguageRequest.

        Args:
            request_data: Request dictionary from RequestSimulator

        Returns:
            NaturalLanguageRequest object
        """
        # Extract natural language text
        nl_text = request_data.get('request', '')

        # Helper function to extract POI name
        def get_poi_name(poi_data):
            if poi_data is None:
                return None
            if isinstance(poi_data, dict):
                return poi_data.get('name')
            if isinstance(poi_data, str):
                return poi_data
            return None

        # Get coordinates with fallback to zone centers
        pickup_lat = request_data.get('pickup_lat', 0.0)
        pickup_lon = request_data.get('pickup_lon', 0.0)

        # If coordinates are missing or zero, use zone center
        if pickup_lat == 0.0 or pickup_lon == 0.0:
            pickup_zone_id = request_data.get('pickup_zone_id')
            if pickup_zone_id:
                pickup_lat, pickup_lon = self._get_zone_center(
                    pickup_zone_id,
                    request_data.get('pickup_zone')
                )

        dropoff_lat = request_data.get('dropoff_lat', 0.0)
        dropoff_lon = request_data.get('dropoff_lon', 0.0)

        # If coordinates are missing or zero, use zone center
        if dropoff_lat == 0.0 or dropoff_lon == 0.0:
            dropoff_zone_id = request_data.get('dropoff_zone_id')
            if dropoff_zone_id:
                dropoff_lat, dropoff_lon = self._get_zone_center(
                    dropoff_zone_id,
                    request_data.get('dropoff_zone')
                )

        # Create ground truth structured request
        ground_truth = StructuredRequest(
            request_id=str(request_data.get('trip_id', '')),
            request_time=request_data.get('request_time', datetime.now()),
            origin=Location(
                latitude=pickup_lat,
                longitude=pickup_lon,
                zone_id=request_data.get('pickup_zone_id'),
                zone_name=request_data.get('pickup_zone'),
                address=request_data.get('pickup_address'),
                poi_name=get_poi_name(request_data.get('pickup_poi'))
            ),
            destination=Location(
                latitude=dropoff_lat,
                longitude=dropoff_lon,
                zone_id=request_data.get('dropoff_zone_id'),
                zone_name=request_data.get('dropoff_zone'),
                address=request_data.get('dropoff_address'),
                poi_name=get_poi_name(request_data.get('dropoff_poi'))
            ),
            requested_pickup_time=request_data.get('requested_pickup_time'),
            requested_dropoff_time=request_data.get('requested_dropoff_time'),
            has_arrival_constraint=request_data.get('has_arrival_constraint', False),
            passenger_count=request_data.get('passenger_count', 1),
            wheelchair_accessible=(request_data.get('wav_request_flag') == 'Y'),
            shared_ride_ok=(request_data.get('shared_request_flag') != 'N'),
            customer_id=request_data.get('customer_id'),
        )

        return NaturalLanguageRequest(
            request_id=str(request_data.get('trip_id', '')),
            request_time=request_data.get('request_time', datetime.now()),
            natural_language_text=nl_text,
            ground_truth=ground_truth
        )

    def _print_summary(self, summary: Dict[str, Any]):
        """Print evaluation summary."""
        print(f"\nOverall Score: {summary['overall_score']:.2f}/100")

        print("\n--- Parsing Metrics ---")
        parsing = summary['parsing_metrics']
        print(f"  Origin Zone Accuracy: {parsing['origin_zone_accuracy']*100:.1f}%")
        print(f"  Destination Zone Accuracy: {parsing['destination_zone_accuracy']*100:.1f}%")
        print(f"  Time Constraint Accuracy: {parsing['time_constraint_accuracy']*100:.1f}%")
        print(f"  Special Requirements Accuracy: {parsing['special_requirements_accuracy']*100:.1f}%")
        print(f"  Mean Origin Error: {parsing['mean_origin_error_miles']:.2f} miles")
        print(f"  Mean Destination Error: {parsing['mean_destination_error_miles']:.2f} miles")

        print("\n--- Routing Metrics ---")
        routing = summary['routing_metrics']
        print(f"  Total Revenue: ${routing['total_revenue']:.2f}")
        print(f"  Total Idle Cost: ${routing['total_idle_cost']:.2f}")
        print(f"  Net Revenue: ${routing['net_revenue']:.2f}")
        print(f"  Deadhead Ratio: {routing['deadhead_ratio']*100:.1f}%")
        print(f"  Average Pickup Time: {routing['average_pickup_time_minutes']:.1f} minutes")
        print(f"  Revenue per Mile: ${routing['revenue_per_mile']:.2f}")

    def _make_serializable(self, obj: Any) -> Any:
        """Make object JSON serializable."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._make_serializable(item) for item in obj]
        else:
            return obj

    def __repr__(self) -> str:
        return (f"GreenAgentEnvironment(vehicles={len(self.vehicle_database)}, "
                f"requests_processed={len(self.processed_requests)})")
