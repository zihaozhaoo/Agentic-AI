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
from tqdm import tqdm

from request_simulation import RequestSimulator
from request_simulation.zone_coordinates import (
    get_zone_coordinate,
    get_borough_bounds,
    get_borough_center,
    BOROUGH_LAND_BOUNDS
)
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
        # Keep active assignments so vehicles stay busy until simulated completion
        self.active_assignments: Dict[str, Dict[str, Any]] = {}

    def initialize_vehicles(
        self,
        num_vehicles: int,
        zone_distribution: Optional[Dict[int, float]] = None,
        wheelchair_accessible_ratio: float = 0.1,
        sample_parquet_path: Optional[str] = None,
        sample_size: int = 1000,
        prefer_uniform_distribution: bool = True
    ):
        """
        Initialize the vehicle fleet.

        Args:
            num_vehicles: Number of vehicles to create
            zone_distribution: Distribution of vehicles across zones
            wheelchair_accessible_ratio: Ratio of wheelchair accessible vehicles
            sample_parquet_path: Optional path to sample trip data for realistic locations
            sample_size: Number of trips to sample for location distribution
            prefer_uniform_distribution: If True, seed vehicles evenly across taxi zones to avoid
                clustering around historical hotspots.
        """
        print(f"Initializing {num_vehicles} vehicles...")

        # Get taxi zone lookup from request simulator
        taxi_zone_lookup = self.request_simulator.preprocessor.zone_lookup

        # Default to an even zone distribution to keep the starting fleet spread out
        zone_distribution = zone_distribution or self._build_uniform_zone_distribution(taxi_zone_lookup)

        # Seed initial locations evenly across taxi zones when requested
        initial_locations = None
        if prefer_uniform_distribution:
            initial_locations = self._generate_even_initial_locations(num_vehicles, taxi_zone_lookup)

        # Optionally sample initial locations from historical trips if uniform seeding is disabled
        if sample_parquet_path and initial_locations is None:
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
        verbose: bool = True,
        map_output_dir: Optional[str] = None,
        inter_request_delay_seconds: float = 0.0
    ) -> Dict[str, Any]:
        """
        Run complete evaluation of a white agent.

        Args:
            white_agent: White agent to evaluate
            requests: List of request dictionaries from RequestSimulator
            start_time: Simulation start time (uses first request time if None)
            end_time: Simulation end time (uses last request time if None)
            verbose: Whether to print progress
            map_output_dir: Optional path; if provided, export trajectories JSON and an interactive HTML map

        Returns:
            Dictionary with evaluation results
        """
        if not requests:
            raise ValueError("No requests provided for evaluation")

        # Sort requests chronologically so the simulator can advance and keep vehicles busy
        requests_sorted = sorted(requests, key=lambda r: self._to_datetime(r.get('request_time')))

        # Set simulation time bounds and clear any previous run state
        self.simulation_start_time = start_time or self._to_datetime(requests_sorted[0].get('request_time'))
        last_request_time = self._to_datetime(requests_sorted[-1].get('request_time'))
        self.simulation_end_time = end_time or (last_request_time + timedelta(minutes=120))
        self.current_time = self.simulation_start_time
        self.active_assignments.clear()

        if verbose:
            print("\n" + "="*80)
            print(f"STARTING EVALUATION: {white_agent.agent_name}")
            print("="*80)
            print(f"  Total requests: {len(requests_sorted)}")
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
            # Snapshot initial fleet state for timeline visualizations.
            for vehicle in self.vehicle_database.get_all_vehicles():
                self.logger.log_vehicle_initialization(
                    vehicle_id=vehicle.vehicle_id,
                    location={
                        'latitude': vehicle.current_location.latitude,
                        'longitude': vehicle.current_location.longitude,
                        'zone_id': vehicle.current_location.zone_id,
                        'zone_name': vehicle.current_location.zone_name,
                    },
                    wheelchair_accessible=vehicle.wheelchair_accessible
                )

        # Reset evaluator
        self.evaluator.reset()
        self.processed_requests.clear()

        # Process each request
        for i, request_data in tqdm(enumerate(requests_sorted), total=len(requests_sorted)):
            # Convert to NaturalLanguageRequest
            nl_request = self._convert_to_nl_request(request_data)

            # Advance simulation to the current request time, processing any vehicle events
            # that occur before this request arrives
            self._advance_to_time_with_events(nl_request.request_time)

            # Log request arrival
            self.logger.log_request_arrival(
                request_id=nl_request.request_id,
                request_time=nl_request.request_time,
                natural_language_text=nl_request.natural_language_text,
                ground_truth=nl_request.ground_truth.to_dict() if nl_request.ground_truth else None
            )

            if verbose and (i + 1) % 50 == 0:
                print(f"  Processing request {i + 1} / {len(requests_sorted)}...")

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
                # Note: This logs the agent's estimated pickup time for comparison with actual
                vehicle = self.vehicle_database.get_vehicle_by_id(routing_decision.vehicle_id)
                if vehicle:
                    self.logger.log_vehicle_assignment(
                        vehicle_id=routing_decision.vehicle_id,
                        request_id=nl_request.request_id,
                        assignment_time=self.current_time,
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

                # Ensure the routing execution succeeded before tracking as active
                if not execution_result.get('success', True):
                    raise RuntimeError(execution_result.get('error', 'Vehicle execution failed'))

                # Track assignment so the vehicle stays busy until the simulated dropoff completes
                self.active_assignments[nl_request.request_id] = {
                    'nl_request': nl_request,
                    'parsed_request': parsed_request,
                    'routing_decision': routing_decision,
                    'execution_result': execution_result
                }

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

            # Optional pacing between requests
            if inter_request_delay_seconds > 0 and (i + 1) < len(requests_sorted):
                time.sleep(inter_request_delay_seconds)

        # Advance through the remaining horizon to complete outstanding trips
        self._advance_to_time_with_events(self.simulation_end_time)

        # Force-complete any residual trips that exceeded the horizon
        if self.active_assignments:
            for request_id in list(self.active_assignments.keys()):
                forced_result = self.vehicle_simulator.simulate_trip_completion(
                    request_id,
                    self.simulation_end_time
                )
                if forced_result:
                    self._finalize_completed_trip(forced_result)
            self.active_assignments.clear()

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

        # Optional map/trajectory export
        if map_output_dir:
            viz_paths = self.export_visualizations(map_output_dir)
            # Also persist full event log for debugging/analysis
            try:
                self.logger.save_json_log(str(Path(map_output_dir) / "events.json"))
            except Exception as log_exc:
                self.logger.log_error(
                    error_type="EVENT_LOG_SAVE_ERROR",
                    error_message=str(log_exc),
                    context={"output_dir": map_output_dir},
                )
            if verbose:
                print(f"\nVisualization exported:")
                print(f"  - Trajectories JSON: {viz_paths['trajectories_json']}")
                print(f"  - HTML map:          {viz_paths['map_html']}")

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
        augment_location: bool = False,
        mean_interarrival_seconds: Optional[float] = 15.0,
        start_time: Optional[datetime] = None,
        uniform_zone_sampling: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Generate requests from trip data.

        This is a convenience method that wraps RequestSimulator.

        Args:
            parquet_path: Path to parquet file with trip data
            n_requests: Number of requests to generate
            augment_location: Whether to augment with exact coordinates (defaults to False to avoid external APIs)
            mean_interarrival_seconds: Target mean interarrival time to control demand intensity
            start_time: Optional fixed start time for the generated timeline
            uniform_zone_sampling: Whether to flatten pickup distribution across taxi zones

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
            augment_location=augment_location,
            mean_interarrival_seconds=mean_interarrival_seconds,
            start_time=start_time,
            uniform_zone_sampling=uniform_zone_sampling
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

    def _build_uniform_zone_distribution(self, taxi_zone_lookup) -> Dict[int, float]:
        """
        Build a uniform distribution over taxi zones to start vehicles evenly.

        Args:
            taxi_zone_lookup: DataFrame containing LocationID entries

        Returns:
            Dictionary mapping zone_id to equal weight
        """
        # Spread probability mass uniformly across all valid LocationIDs
        distribution: Dict[int, float] = {}
        for zone_id in taxi_zone_lookup.get('LocationID', []):
            try:
                distribution[int(zone_id)] = 1.0
            except (TypeError, ValueError):
                continue
        return distribution or {1: 1.0}

    def _generate_even_initial_locations(
        self,
        num_vehicles: int,
        taxi_zone_lookup
    ) -> List[Location]:
        """
        Generate initial vehicle locations that cycle through taxi zones to avoid clustering.

        Uses zone-specific centroids when available, otherwise samples from land-only
        borough bounds to prevent vehicles from spawning in water.

        Args:
            num_vehicles: Fleet size
            taxi_zone_lookup: DataFrame of zone metadata

        Returns:
            List of Location objects covering the zone catalog
        """
        # Cycle through zones so every zone is represented before repeating
        zone_records = taxi_zone_lookup[['LocationID', 'Borough', 'Zone']].dropna(subset=['LocationID']).to_dict('records')
        if not zone_records:
            return []

        locations: List[Location] = []
        for idx in range(num_vehicles):
            zone = zone_records[idx % len(zone_records)]
            zone_id = int(zone.get('LocationID', 0))
            borough = zone.get('Borough', 'Manhattan')

            # Use zone-specific coordinate with small jitter to spread vehicles
            lat, lon = get_zone_coordinate(zone_id, borough, jitter=0.003)

            locations.append(Location(
                latitude=lat,
                longitude=lon,
                zone_id=zone_id,
                zone_name=zone.get('Zone', 'Unknown')
            ))

        # Shuffle so early assignments are not biased toward any borough/zone
        random.shuffle(locations)
        return locations

    def _get_zone_center(self, zone_id: int, zone_name: str = None) -> tuple[float, float]:
        """
        Get approximate center coordinates for a taxi zone.

        Uses zone-specific centroids when available, otherwise falls back to
        land-only borough sampling to prevent points falling in water.

        Args:
            zone_id: Taxi zone ID
            zone_name: Optional zone name for fallback

        Returns:
            (latitude, longitude) tuple guaranteed to be on land
        """
        # Try to get borough from zone lookup for fallback
        borough = None
        try:
            zone_lookup = self.request_simulator.preprocessor.zone_lookup
            zone_info = zone_lookup[zone_lookup['LocationID'] == zone_id]

            if len(zone_info) > 0:
                borough = zone_info.iloc[0].get('Borough', 'Manhattan')
        except Exception as e:
            self.logger.log_error(
                error_type='ZONE_CENTER_LOOKUP_ERROR',
                error_message=str(e),
                context={'zone_id': zone_id}
            )

        # Use centralized zone coordinate lookup with small jitter
        return get_zone_coordinate(zone_id, borough, jitter=0.002)

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

        request_time = self._to_datetime(request_data.get('request_time', datetime.now()))

        return NaturalLanguageRequest(
            request_id=str(request_data.get('trip_id', '')),
            request_time=request_time,
            natural_language_text=nl_text,
            ground_truth=ground_truth
        )

    def _advance_to_time(self, target_time: datetime):
        """
        Advance the simulator clock to a target time and finalize any completed trips.

        Args:
            target_time: Simulation timestamp to advance to
        """
        # Skip when the clock has not started yet
        if self.current_time is None:
            self.current_time = target_time
            return

        # Ignore requests that arrive earlier than the current clock to preserve causality
        if target_time < self.current_time:
            return

        # Move the simulator forward and collect trips that finished in this window
        time_delta = target_time - self.current_time
        completed_trips = self.vehicle_simulator.advance_time(self.current_time, time_delta)
        self.current_time = target_time

        # Finalize completed trips so vehicles become available again
        for trip_result in completed_trips:
            self._finalize_completed_trip(trip_result)

    def _advance_to_time_with_events(self, target_time: datetime):
        """
        Advance the simulator clock to a target time, processing vehicle events at their exact times.
        
        This method implements event-driven simulation by:
        1. Collecting all vehicle events (pickups, dropoffs) that occur before target_time
        2. Advancing time incrementally to each event
        3. Processing events at their exact scheduled times
        
        This ensures accurate timestamps in trajectories and prevents event timestamp collapse.

        Args:
            target_time: Simulation timestamp to advance to
        """
        # Skip when the clock has not started yet
        if self.current_time is None:
            self.current_time = target_time
            return

        # Ignore requests that arrive earlier than the current clock to preserve causality
        if target_time < self.current_time:
            return

        # Collect all upcoming vehicle events between current_time and target_time
        while self.current_time < target_time:
            next_event_time = self._get_next_vehicle_event_time()
            
            # If no events or next event is after target, advance directly to target
            if next_event_time is None or next_event_time >= target_time:
                self._advance_to_time(target_time)
                break
            
            # Guard against infinite loop: skip events in the past.
            # Note: next_event_time == self.current_time is valid (events due "now").
            if next_event_time < self.current_time:
                # This shouldn't happen, but if it does, log error and advance to target
                self.logger.log_error(
                    error_type='INVALID_EVENT_TIME',
                    error_message=f'Next event time {next_event_time} is not after current time {self.current_time}',
                    context={'next_event_time': next_event_time.isoformat(), 'current_time': self.current_time.isoformat()}
                )
                self._advance_to_time(target_time)
                break

            # Events scheduled exactly at the current clock are due now; process them without advancing the clock.
            if next_event_time == self.current_time:
                self._advance_to_time(self.current_time)
                continue
            
            # Otherwise, advance to the next event time
            self._advance_to_time(next_event_time)

    def _get_next_vehicle_event_time(self) -> Optional[datetime]:
        """
        Get the timestamp of the next vehicle event (pickup or dropoff).
        
        Returns:
            Datetime of next event, or None if no pending events
        """
        next_time = None
        
        # Check all active trips for their next event time
        for trip_info in self.vehicle_simulator.active_trips.values():
            if trip_info['status'] == 'en_route_to_pickup':
                event_time = trip_info.get('estimated_pickup_time')
                if event_time and (next_time is None or event_time < next_time):
                    next_time = event_time
            elif trip_info['status'] == 'on_trip':
                event_time = trip_info.get('estimated_dropoff_time')
                if event_time and (next_time is None or event_time < next_time):
                    next_time = event_time
        
        return next_time

    def _finalize_completed_trip(self, trip_result: Dict[str, Any]):
        """
        Handle bookkeeping, logging, and evaluation when a trip finishes.

        Args:
            trip_result: Trip dictionary returned by the vehicle simulator
        """
        # Extract assignment context for evaluation/logging
        request_id = trip_result.get('request_id')
        assignment = self.active_assignments.pop(request_id, None)
        if not assignment:
            return

        nl_request = assignment['nl_request']
        parsed_request = assignment['parsed_request']
        routing_decision = assignment['routing_decision']

        # Emit trip completion log entry with pickup/dropoff positions
        self.logger.log_trip_completion(
            vehicle_id=routing_decision.vehicle_id,
            request_id=nl_request.request_id,
            trip_distance=trip_result.get('trip_distance', 0),
            trip_time=trip_result.get('trip_time', 0),
            fare=trip_result.get('fare', 0),
            deadhead_miles=trip_result.get('deadhead_miles', 0),
            pickup_time=trip_result.get('actual_pickup_time_timestamp'),
            completion_time=trip_result.get('completion_time'),
            pickup_location={
                'latitude': parsed_request.origin.latitude,
                'longitude': parsed_request.origin.longitude
            },
            dropoff_location={
                'latitude': parsed_request.destination.latitude,
                'longitude': parsed_request.destination.longitude
            }
        )

        # Evaluate the request now that we have trip execution details
        self.evaluator.evaluate_request(
            nl_request,
            parsed_request,
            routing_decision,
            trip_result
        )

        # Log per-request score to maintain parity with prior behavior
        trip_miles = trip_result.get('trip_distance', 0)
        deadhead_miles = trip_result.get('deadhead_miles', 0)
        denom = trip_miles + deadhead_miles
        trip_share = (trip_miles / denom) if denom > 0 else 0
        parse_ok = self._is_parse_correct(parsed_request, nl_request)
        per_request_score = (1.0 if parse_ok else 0.0) * trip_share
        self.logger.log_event(
            'REQUEST_SCORE',
            {
                'request_id': nl_request.request_id,
                'score': per_request_score,
                'trip_miles': trip_miles,
                'deadhead_miles': deadhead_miles,
                'parse_ok': parse_ok
            }
        )

        # Track processed request outcome
        self.processed_requests.append({
            'request_id': nl_request.request_id,
            'success': True,
            'parsed_request': parsed_request.to_dict(),
            'routing_decision': routing_decision.to_dict(),
            'execution_result': assignment.get('execution_result'),
            'trip_result': trip_result,
        })

    def _is_parse_correct(self, parsed_request: StructuredRequest, nl_request: NaturalLanguageRequest) -> bool:
        """
        Determine whether the parsed request matches the ground truth zones.

        Args:
            parsed_request: Structured request predicted by the white agent
            nl_request: Original natural language request with ground truth

        Returns:
            True if both origin and destination zones are parsed correctly
        """
        if not nl_request.ground_truth:
            return False

        parse_ok = (
            parsed_request.origin.zone_id == nl_request.ground_truth.origin.zone_id and
            parsed_request.destination.zone_id == nl_request.ground_truth.destination.zone_id
        )
        return parse_ok

    def _to_datetime(self, value: Any) -> datetime:
        """
        Normalize timestamp-like inputs to datetime objects.

        Args:
            value: Datetime, pandas Timestamp, or None

        Returns:
            Native datetime for consistent comparisons
        """
        if value is None:
            return datetime.now()
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except Exception:
                return datetime.now()
        if hasattr(value, "to_pydatetime"):
            return value.to_pydatetime()
        return value

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

    def export_visualizations(
        self,
        output_dir: str,
        map_filename: str = "trajectories_map.html",
        trajectories_filename: str = "trajectories.json",
        center_lat: float = 40.7589,
        center_lon: float = -73.9851,
        zoom: int = 11
    ) -> Dict[str, str]:
        """
        Export trajectory data and an interactive HTML map animation.

        Args:
            output_dir: Directory to write files into
            map_filename: HTML file name for the map
            trajectories_filename: JSON file name for trajectory data
            center_lat/center_lon: Map center (NYC by default)
            zoom: Initial map zoom level

        Returns:
            Dict with paths to generated files.
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        trajectories_path = output_path / trajectories_filename
        map_path = output_path / map_filename

        self.logger.export_trajectories_json(str(trajectories_path))
        self.logger.export_map_html(str(map_path), center_lat=center_lat, center_lon=center_lon, zoom=zoom)

        return {
            'trajectories_json': str(trajectories_path),
            'map_html': str(map_path)
        }

    def __repr__(self) -> str:
        return (f"GreenAgentEnvironment(vehicles={len(self.vehicle_database)}, "
                f"requests_processed={len(self.processed_requests)})")
