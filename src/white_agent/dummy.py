import sys
import os
import numpy as np
import pandas as pd
import re
import random

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class Vehicle:
    """Represents a single vehicle in the fleet."""

    def __init__(self, vehicle_id):
        self.vehicle_id = vehicle_id
        self.current_location = 0  # Start at depot (node 0)
        self.available_time = 0  # Available from time 0 (in minutes from midnight)
        self.assigned_requests = []  # List of request IDs assigned to this vehicle

    def __repr__(self):
        return f"Vehicle({self.vehicle_id}, loc={self.current_location}, avail={self.available_time}, requests={self.assigned_requests})"


class DummyAgent:
    """
    Dummy agent that assigns incoming requests to vehicles based on simple feasibility checks.

    Node encoding:
    - Node 0: depot
    - Node 2k-1: pickup for request k (k=1,2,...,n)
    - Node 2k: dropoff for request k
    """

    def __init__(self, num_vehicles=10):
        self.num_vehicles = num_vehicles
        self.vehicles = [Vehicle(i+1) for i in range(num_vehicles)]
        self.distance_matrix = None  # Travel time matrix in minutes
        self.requests_data = None

    def load_data(self, distance_matrix_path, requests_csv_path):
        """Load distance matrix and requests data."""
        # Load distance matrix (travel time in minutes)
        self.distance_matrix = np.load(distance_matrix_path)
        print(f"Loaded distance matrix: {self.distance_matrix.shape}")

        # Load requests
        self.requests_data = pd.read_csv(requests_csv_path)
        print(f"Loaded {len(self.requests_data)} requests from CSV")

    def parse_time_window(self, time_window_str):
        """
        Parse time window string '[start, end]' to extract start and end timestamps.
        Returns (start_minutes, end_minutes) from midnight.
        """
        match = re.match(r'\[(\d+),\s*(\d+)\]', time_window_str)
        if not match:
            return None, None

        start_ts = int(match.group(1))
        end_ts = int(match.group(2))

        # Convert Unix timestamps to minutes from midnight
        from datetime import datetime
        start_dt = datetime.fromtimestamp(start_ts)
        end_dt = datetime.fromtimestamp(end_ts)

        # Minutes from midnight
        start_minutes = start_dt.hour * 60 + start_dt.minute
        end_minutes = end_dt.hour * 60 + end_dt.minute

        return start_minutes, end_minutes

    def get_travel_time(self, from_node, to_node):
        """Get travel time between two nodes from distance matrix."""
        if from_node >= len(self.distance_matrix) or to_node >= len(self.distance_matrix):
            return float('inf')
        return self.distance_matrix[from_node][to_node]

    def check_feasibility(self, vehicle, pickup_node, dropoff_node,
                          pickup_tw_start, pickup_tw_end,
                          dropoff_tw_start, dropoff_tw_end):
        """
        Check if a vehicle can feasibly serve a request.

        Feasibility criteria:
        - Vehicle must be able to reach pickup location before pickup time window ends
        - Time between vehicle's next available time and pickup time window start >= travel time
        """
        # Get travel time from vehicle's current location to pickup
        travel_time_to_pickup = self.get_travel_time(vehicle.current_location, pickup_node)

        # Vehicle needs to arrive at pickup before pickup time window ends
        arrival_time = vehicle.available_time + travel_time_to_pickup

        # Check if vehicle can arrive within pickup time window
        # We need: arrival_time <= pickup_tw_end
        # Also: arrival_time >= pickup_tw_start (can't arrive too early, or need to wait)
        if arrival_time > pickup_tw_end:
            return False

        # Additional check: ensure there's enough time to complete the trip
        # (pickup to dropoff) and arrive before dropoff window ends
        travel_time_pickup_to_dropoff = self.get_travel_time(pickup_node, dropoff_node)

        # Earliest we can start the trip is max(arrival_time, pickup_tw_start)
        actual_pickup_time = max(arrival_time, pickup_tw_start)
        dropoff_arrival_time = actual_pickup_time + travel_time_pickup_to_dropoff

        # Check if we can arrive before dropoff window ends
        if dropoff_arrival_time > dropoff_tw_end:
            return False

        return True

    def assign_request(self, request_idx):
        """
        Assign a request to a random feasible vehicle.

        Returns the vehicle ID if successful, None otherwise.
        """
        row = self.requests_data.iloc[request_idx]

        # Parse time windows
        pickup_tw_start, pickup_tw_end = self.parse_time_window(row['pickup_time_window'])
        dropoff_tw_start, dropoff_tw_end = self.parse_time_window(row['dropoff_time_window'])

        if pickup_tw_start is None or dropoff_tw_start is None:
            print(f"Warning: Could not parse time windows for request {request_idx + 1}")
            return None

        # Calculate node indices
        request_num = request_idx + 1
        pickup_node = 2 * request_num - 1
        dropoff_node = 2 * request_num

        # Find feasible vehicles
        feasible_vehicles = []
        for vehicle in self.vehicles:
            if self.check_feasibility(
                vehicle, pickup_node, dropoff_node,
                pickup_tw_start, pickup_tw_end,
                dropoff_tw_start, dropoff_tw_end
            ):
                feasible_vehicles.append(vehicle)

        if not feasible_vehicles:
            print(f"Request {request_num}: No feasible vehicles found")
            return None

        # Randomly select one feasible vehicle
        selected_vehicle = random.choice(feasible_vehicles)

        # Update vehicle state
        travel_time_to_pickup = self.get_travel_time(selected_vehicle.current_location, pickup_node)
        arrival_time_at_pickup = selected_vehicle.available_time + travel_time_to_pickup
        actual_pickup_time = max(arrival_time_at_pickup, pickup_tw_start)

        travel_time_to_dropoff = self.get_travel_time(pickup_node, dropoff_node)
        dropoff_time = actual_pickup_time + travel_time_to_dropoff

        # Update vehicle
        selected_vehicle.current_location = dropoff_node
        selected_vehicle.available_time = max(dropoff_time, dropoff_tw_start)
        selected_vehicle.assigned_requests.append(request_num)

        print(f"Request {request_num}: Assigned to Vehicle {selected_vehicle.vehicle_id} "
              f"(feasible: {len(feasible_vehicles)} vehicles)")

        return selected_vehicle.vehicle_id

    def run(self):
        """Process all requests and assign them to vehicles."""
        print("\n" + "="*80)
        print("DUMMY AGENT: Sequential Request Assignment")
        print("="*80)

        assignments = {}
        unassigned = []

        for idx in range(len(self.requests_data)):
            vehicle_id = self.assign_request(idx)
            if vehicle_id is not None:
                if vehicle_id not in assignments:
                    assignments[vehicle_id] = []
                assignments[vehicle_id].append(idx + 1)
            else:
                unassigned.append(idx + 1)

        # Print results
        print("\n" + "="*80)
        print("ASSIGNMENT RESULTS")
        print("="*80)

        print(f"\nTotal Requests: {len(self.requests_data)}")
        print(f"Assigned: {len(self.requests_data) - len(unassigned)}")
        print(f"Unassigned: {len(unassigned)}")
        print(f"Vehicles Used: {len(assignments)}")

        print("\nroutes: {")
        for vehicle_id in sorted(assignments.keys()):
            requests = assignments[vehicle_id]
            route_str = ", ".join(map(str, requests))
            print(f"  vehicle_{vehicle_id}: [{route_str}],")
        print("}")

        if unassigned:
            print(f"\nUnassigned Requests: {unassigned}")

        # Print vehicle states
        print("\n" + "="*80)
        print("VEHICLE STATES")
        print("="*80)
        for vehicle in self.vehicles:
            if vehicle.assigned_requests:
                print(vehicle)

        return assignments, unassigned


def main():
    """Main function to run the dummy agent."""
    # Set random seed for reproducibility
    random.seed(42)

    # Initialize agent
    agent = DummyAgent(num_vehicles=10)

    # Load data
    data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_sampling'))
    distance_matrix_path = os.path.join(data_dir, 'distance_matrix.npy')
    requests_csv_path = os.path.join(data_dir, 'sampled_requests_with_coords.csv')

    agent.load_data(distance_matrix_path, requests_csv_path)

    # Run assignment
    assignments, unassigned = agent.run()

    # Save results
    output_file = os.path.join(data_dir, 'dummy_agent_solution.txt')
    with open(output_file, 'w') as f:
        f.write("Dummy Agent Solution for Sampled NYC Taxi Requests\n")
        f.write("="*80 + "\n\n")
        f.write(f"Total Requests: {len(agent.requests_data)}\n")
        f.write(f"Assigned: {len(agent.requests_data) - len(unassigned)}\n")
        f.write(f"Unassigned: {len(unassigned)}\n")
        f.write(f"Vehicles Used: {len(assignments)}\n\n")

        f.write("routes: {\n")
        for vehicle_id in sorted(assignments.keys()):
            requests = assignments[vehicle_id]
            route_str = ", ".join(map(str, requests))
            f.write(f"  vehicle_{vehicle_id}: [{route_str}],\n")
        f.write("}\n")

        if unassigned:
            f.write(f"\nUnassigned Requests: {unassigned}\n")

    print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    main()
