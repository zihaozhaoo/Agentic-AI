import sys
import os
import numpy as np
import pandas as pd
from datetime import datetime
import re
import time
from typing import Dict, List
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp


# ==================== OR-Tools Solver Functions ====================
# Adapted from src/solver/or_tools.py

def cost_estimator(
    distance_matrix: np.ndarray,
    requests: List[Dict],
    vehicle_num: int,
    depot_node: int = 0,
    vehicle_travel_speed: float = 20.0,
    time_window_duration: int = 30,
    vehicle_capacity: int = 4,
    max_solve_time: float = 1,
) -> Dict:

    start_wall = time.time()

    sol = _solve_darp_mandatory(
        distance_matrix=distance_matrix,
        depot_node=depot_node,
        requests=requests,
        num_vehicles=vehicle_num,
        vehicle_travel_speed=vehicle_travel_speed,
        time_window_duration=time_window_duration,
        vehicle_capacity=vehicle_capacity,
        max_solve_time=max_solve_time,
    )

    # Compose cost model
    routing_cost_km = sol["total_distance_km"]
    total_cost = routing_cost_km

    # Augment solution dict with cost components
    sol.update(
        {
            "routing_cost": routing_cost_km,
            "total_cost": total_cost,
            "num_vehicles": vehicle_num,
            "solve_time": time.time() - start_wall,
        }
    )

    return sol


def _solve_darp_mandatory(
    distance_matrix: np.ndarray,
    depot_node: int,
    requests: List[Dict],
    num_vehicles: int,
    vehicle_travel_speed: float,
    time_window_duration: int,
    vehicle_capacity: int,
    max_solve_time: float,
) -> Dict:
    """Solve a DARP with mandatory pickup-and-delivery (no dropping)."""

    # Build node sets
    pickup_nodes, dropoff_nodes, node_to_request, request_to_pickup, request_to_dropoff = _create_nodes(requests)
    num_nodes = 1 + len(pickup_nodes) + len(dropoff_nodes)  # depot + pickups + dropoffs
    depot = 0

    manager = pywrapcp.RoutingIndexManager(num_nodes, num_vehicles, depot)
    routing = pywrapcp.RoutingModel(manager)

    # Distance callback (return integer cost). Keep units consistent: use meters as integer arc costs.
    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        if from_node == to_node:
            return 0
        i = _get_node_location(from_node, depot_node, pickup_nodes, dropoff_nodes, node_to_request, requests)
        j = _get_node_location(to_node, depot_node, pickup_nodes, dropoff_nodes, node_to_request, requests)
        if i is None or j is None:
            return 0
        dist_km = float(distance_matrix[i][j])
        return int(round(dist_km * 1000.0))  # meters

    transit_cost = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_cost)

    # Time callback (minutes) using travel speed
    def time_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        if from_node == to_node:
            return 0
        i = _get_node_location(from_node, depot_node, pickup_nodes, dropoff_nodes, node_to_request, requests)
        j = _get_node_location(to_node, depot_node, pickup_nodes, dropoff_nodes, node_to_request, requests)
        if i is None or j is None:
            return 0
        dist_km = float(distance_matrix[i][j])
        # minutes = (km / (km/h)) * 60
        minutes = int(round((dist_km / max(vehicle_travel_speed, 1e-6)) * 60.0))
        return max(0, minutes)

    transit_time = routing.RegisterTransitCallback(time_callback)

    # Time dimension
    # Allow waiting time; set a daily horizon (24h)
    routing.AddDimension(
        transit_time,
        120,    # waiting allowed (buffer)
        1440,   # horizon in minutes
        False,  # do not force start cumul to zero; vehicles can start later
        "Time",
    )
    time_dimension = routing.GetDimensionOrDie("Time")

    # Allow depot at any time in the day
    for v in range(num_vehicles):
        time_dimension.CumulVar(routing.Start(v)).SetRange(0, 1440)
        time_dimension.CumulVar(routing.End(v)).SetRange(0, 1440)

    # Capacity dimension
    def demand_callback(from_index):
        node = manager.IndexToNode(from_index)
        if node == depot:
            return 0
        return 1 if node in pickup_nodes else (-1 if node in dropoff_nodes else 0)

    demand_cb = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_cb,
        0,
        [vehicle_capacity] * num_vehicles,
        True,
        "Capacity",
    )

    # Time windows (clamped to 05:00–20:00 i.e., indices 10..40)
    def clamp_index(idx: int) -> int:
        return max(10, min(40, int(idx)))

    for i, req in enumerate(requests):
        p_node = request_to_pickup[i]
        d_node = request_to_dropoff[i]

        p_idx = clamp_index(req["o_t_index"])
        d_idx = clamp_index(req["d_t_index"])

        p_start = p_idx * time_window_duration
        p_end = p_start + time_window_duration
        d_start = d_idx * time_window_duration
        d_end = d_start + time_window_duration

        time_dimension.CumulVar(manager.NodeToIndex(p_node)).SetRange(p_start, p_end)
        time_dimension.CumulVar(manager.NodeToIndex(d_node)).SetRange(d_start, d_end)

    # Pickup & delivery pairing (mandatory)
    for i in range(len(requests)):
        p_node = request_to_pickup[i]
        d_node = request_to_dropoff[i]
        p_idx = manager.NodeToIndex(p_node)
        d_idx = manager.NodeToIndex(d_node)

        routing.AddPickupAndDelivery(p_idx, d_idx)
        # same vehicle
        routing.solver().Add(routing.VehicleVar(p_idx) == routing.VehicleVar(d_idx))
        # pickup before dropoff in time
        time_dimension.SetCumulVarSoftLowerBound(d_idx, 0, 0)  # no penalty, just initialize var
        routing.solver().Add(time_dimension.CumulVar(p_idx) <= time_dimension.CumulVar(d_idx))

    # Search parameters
    search = pywrapcp.DefaultRoutingSearchParameters()
    search.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
    search.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    # Support fractional seconds for time limit
    _max_time = max(0.0, float(max_solve_time))
    _whole = int(_max_time)
    _nanos = int(round((_max_time - _whole) * 1e9))
    search.time_limit.seconds = _whole
    # OR-Tools Duration supports nanos attribute
    try:
        search.time_limit.nanos = _nanos
    except Exception:
        # Fallback for older OR-Tools builds without nanos field
        pass
    search.log_search = False

    solution = routing.SolveWithParameters(search)

    if solution is None:
        return {
            "status": "INFEASIBLE",
            "total_distance_km": 0.0,
            "num_vehicles_used": 0,
            "routes": [],
        }

    # Extract routes and distance
    routes = []
    total_distance_m = 0
    for v in range(num_vehicles):
        route_nodes = []
        index = routing.Start(v)
        if routing.IsEnd(solution.Value(routing.NextVar(index))):
            # empty vehicle, skip adding an empty route
            continue
        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            if node != depot:
                route_nodes.append(node)
            next_index = solution.Value(routing.NextVar(index))
            total_distance_m += routing.GetArcCostForVehicle(index, next_index, v)
            index = next_index
        if route_nodes:
            routes.append(route_nodes)

    return {
        "status": "FEASIBLE",
        "total_distance_km": total_distance_m / 1000.0,
        "num_vehicles_used": len(routes),
        "routes": routes,
    }


def _create_nodes(requests):
    """Create pickup and dropoff node ids for each request."""
    pickup_nodes = []
    dropoff_nodes = []
    node_to_request = {}
    request_to_pickup = {}
    request_to_dropoff = {}

    # Depot is node 0; we will index pickups 1..N and dropoffs N+1..2N
    depot = 0
    next_node = 1

    for i, req in enumerate(requests):
        p_node = next_node
        d_node = next_node + 1
        next_node += 2
        pickup_nodes.append(p_node)
        dropoff_nodes.append(d_node)
        node_to_request[p_node] = i
        node_to_request[d_node] = i
        request_to_pickup[i] = p_node
        request_to_dropoff[i] = d_node

    return pickup_nodes, dropoff_nodes, node_to_request, request_to_pickup, request_to_dropoff


def _get_node_location(node, depot_node, pickup_nodes, dropoff_nodes, node_to_request, requests):
    """Map a solver node id back to a location index in the distance matrix.

    Returns the index into the distance matrix corresponding to the given node.
    """
    # Depot maps to depot_node
    if node == 0:
        return depot_node

    # Pickup nodes map to the origin location of the corresponding request
    if node in pickup_nodes:
        req_idx = node_to_request.get(node)
        if req_idx is None:
            return None
        return requests[req_idx]["origin"]

    # Dropoff nodes map to the destination location of the corresponding request
    if node in dropoff_nodes:
        req_idx = node_to_request.get(node)
        if req_idx is None:
            return None
        return requests[req_idx]["destination"]

    return None


# ==================== Data Processing Functions ====================

def parse_time_window(time_window_str):
    """
    Parse time window string from CSV format '[start, end]' to get the midpoint.
    Returns the time index (half-hour buckets since midnight).

    Time indices:
    - Index 0 = 00:00-00:30
    - Index 1 = 00:30-01:00
    - Index 10 = 05:00-05:30
    - Index 40 = 20:00-20:30
    """
    # Extract start and end timestamps
    match = re.match(r'\[(\d+),\s*(\d+)\]', time_window_str)
    if not match:
        return None

    start_ts = int(match.group(1))
    end_ts = int(match.group(2))

    # Use midpoint of time window
    mid_ts = (start_ts + end_ts) / 2

    # Convert to datetime
    dt = datetime.fromtimestamp(mid_ts)

    # Calculate time index (half-hour buckets since midnight)
    # Index = (hour * 2) + (0 if minute < 30 else 1)
    time_index = (dt.hour * 2) + (0 if dt.minute < 30 else 1)

    return time_index


def load_and_prepare_data():
    """
    Load the distance matrix and sampled requests, and prepare them for the solver.

    Returns:
    --------
    tuple: (distance_matrix, requests)
        - distance_matrix: numpy array (41x41) with travel times in minutes
        - requests: list of dicts for OR-Tools solver
    """
    # Load distance matrix (travel time in minutes)
    data_sampling_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_sampling'))
    distance_matrix_path = os.path.join(data_sampling_dir, 'distance_matrix.npy')
    distance_matrix = np.load(distance_matrix_path)

    print(f"Loaded distance matrix: {distance_matrix.shape}")
    print(f"Distance matrix represents travel time in MINUTES")

    # Load sampled requests
    csv_path = os.path.join(data_sampling_dir, 'sampled_requests_with_coords.csv')
    df = pd.read_csv(csv_path)

    print(f"Loaded {len(df)} requests from CSV")

    # Convert to OR-Tools format
    # Node encoding:
    #   - Node 0: depot
    #   - Node 2*k-1: pickup for request k (k=1,2,...,n)
    #   - Node 2*k: dropoff for request k
    requests = []

    for idx, row in df.iterrows():
        request_num = idx + 1  # 1-indexed

        # Calculate node indices in distance matrix
        pickup_node = 2 * request_num - 1
        dropoff_node = 2 * request_num

        # Parse time windows
        pickup_time_idx = parse_time_window(row['pickup_time_window'])
        dropoff_time_idx = parse_time_window(row['dropoff_time_window'])

        if pickup_time_idx is None or dropoff_time_idx is None:
            print(f"Warning: Could not parse time windows for request {request_num}, skipping")
            continue

        request = {
            'origin': pickup_node,
            'destination': dropoff_node,
            'o_t_index': pickup_time_idx,
            'd_t_index': dropoff_time_idx,
        }
        requests.append(request)

    print(f"Prepared {len(requests)} requests for solver")
    print(f"\nSample request:")
    if requests:
        print(f"  Request 1: pickup node {requests[0]['origin']}, dropoff node {requests[0]['destination']}")
        print(f"  Time indices: pickup {requests[0]['o_t_index']}, dropoff {requests[0]['d_t_index']}")

    return distance_matrix, requests


def format_time_from_index(time_index):
    """Convert time index to human-readable time string."""
    hour = time_index // 2
    minute = 0 if (time_index % 2) == 0 else 30
    return f"{hour:02d}:{minute:02d}"


def print_solution(result, requests):
    """Print the routing solution in a readable format."""
    print("\n" + "="*80)
    print("ROUTING SOLUTION")
    print("="*80)

    print(f"\nStatus: {result['status']}")
    print(f"Total Cost: {result['total_cost']:.2f} (units: travel time)")
    print(f"Routing Cost: {result['routing_cost']:.2f}")
    print(f"Number of Vehicles Used: {result['num_vehicles_used']}")
    print(f"Solve Time: {result['solve_time']:.2f} seconds")

    if result['status'] == 'FEASIBLE' and 'routes' in result:
        print(f"\nroutes: {{")

        for v_idx, route in enumerate(result['routes']):
            # Extract unique request IDs from this route
            request_ids = []
            seen_requests = set()

            for node in route:
                # Calculate request number from node
                # Odd nodes (pickups): request = (node + 1) // 2
                # Even nodes (dropoffs): request = node // 2
                if node % 2 == 1:  # Pickup
                    request_num = (node + 1) // 2
                else:  # Dropoff
                    request_num = node // 2

                # Add request to list if not already seen
                if request_num not in seen_requests:
                    request_ids.append(request_num)
                    seen_requests.add(request_num)

            # Format and print the route
            route_str = ", ".join(map(str, request_ids))
            print(f"  vehicle_{v_idx + 1}: [{route_str}],")

        print("}")

    print("\n" + "="*80)


def main():
    """Main function to solve vehicle routing problem for sampled requests."""
    print("Vehicle Routing Problem Solver for Sampled NYC Taxi Requests")
    print("="*80)

    # Load data
    distance_matrix, requests = load_and_prepare_data()

    if len(requests) == 0:
        print("Error: No valid requests to route")
        return

    # Solver parameters
    num_vehicles = 10
    depot_node = 0

    # IMPORTANT: Our distance_matrix contains TRAVEL TIME in minutes, not distance in km.
    # To make the solver work correctly, we treat "1 minute" as "1 km" and set
    # vehicle_travel_speed = 60 km/h, so the time calculation becomes:
    #   time = (distance / speed) * 60 = (1 km / 60 km/h) * 60 min/h = 1 minute
    # This way the time constraints work correctly.
    vehicle_travel_speed = 60.0  # km/h (conceptual mapping)

    max_solve_time = 30.0  # seconds
    time_window_duration = 30  # minutes
    vehicle_capacity = 4  # passengers

    print(f"\n--- Solver Parameters ---")
    print(f"Number of Vehicles: {num_vehicles}")
    print(f"Depot Node: {depot_node}")
    print(f"Vehicle Capacity: {vehicle_capacity} passengers")
    print(f"Time Window Duration: {time_window_duration} minutes")
    print(f"Max Solve Time: {max_solve_time} seconds")

    # Call the solver
    print(f"\n--- Running OR-Tools Solver ---")
    print("This may take a few seconds...")

    result = cost_estimator(
        distance_matrix=distance_matrix,
        requests=requests,
        vehicle_num=num_vehicles,
        depot_node=depot_node,
        vehicle_travel_speed=vehicle_travel_speed,
        time_window_duration=time_window_duration,
        vehicle_capacity=vehicle_capacity,
        max_solve_time=max_solve_time,
    )

    # Print solution
    print_solution(result, requests)

    # Save results to file
    output_dir = os.path.join(os.path.dirname(__file__), '..', 'data_sampling')
    output_file = os.path.join(output_dir, 'routing_solution.txt')

    with open(output_file, 'w') as f:
        f.write("Vehicle Routing Solution for Sampled NYC Taxi Requests\n")
        f.write("="*80 + "\n\n")
        f.write(f"Status: {result['status']}\n")
        f.write(f"Total Cost: {result['total_cost']:.2f}\n")
        f.write(f"Routing Cost: {result['routing_cost']:.2f}\n")
        f.write(f"Number of Vehicles Used: {result['num_vehicles_used']}\n")
        f.write(f"Solve Time: {result['solve_time']:.2f} seconds\n\n")

        if result['status'] == 'FEASIBLE' and 'routes' in result:
            f.write("routes: {\n")
            for v_idx, route in enumerate(result['routes']):
                # Extract unique request IDs from this route
                request_ids = []
                seen_requests = set()

                for node in route:
                    # Calculate request number from node
                    if node % 2 == 1:  # Pickup
                        request_num = (node + 1) // 2
                    else:  # Dropoff
                        request_num = node // 2

                    # Add request to list if not already seen
                    if request_num not in seen_requests:
                        request_ids.append(request_num)
                        seen_requests.add(request_num)

                # Format and write the route
                route_str = ", ".join(map(str, request_ids))
                f.write(f"  vehicle_{v_idx + 1}: [{route_str}],\n")

            f.write("}\n")

    print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    main()
