import sys
import os
import numpy as np
import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from white_agent.dummy import DummyAgent


def calculate_routing_cost(assignments, distance_matrix, num_vehicles=10):
    """
    Calculate the total routing cost based on vehicle assignments.

    Parameters:
    -----------
    assignments : dict
        Dictionary mapping vehicle_id to list of request IDs
    distance_matrix : numpy.ndarray
        Travel time matrix (in minutes)
    num_vehicles : int
        Total number of vehicles

    Returns:
    --------
    dict : Dictionary with routing cost details
    """
    depot_node = 0
    total_cost = 0
    vehicle_costs = {}

    print("\n" + "="*80)
    print("ROUTING COST CALCULATION")
    print("="*80)

    for vehicle_id in range(1, num_vehicles + 1):
        if vehicle_id not in assignments or not assignments[vehicle_id]:
            # Vehicle not used
            vehicle_costs[vehicle_id] = 0
            continue

        request_ids = assignments[vehicle_id]
        vehicle_cost = 0
        current_node = depot_node

        # Build the route for this vehicle
        route_nodes = [depot_node]

        for request_id in request_ids:
            # For each request, visit pickup then dropoff
            pickup_node = 2 * request_id - 1
            dropoff_node = 2 * request_id

            route_nodes.append(pickup_node)
            route_nodes.append(dropoff_node)

        # Return to depot
        route_nodes.append(depot_node)

        # Calculate cost for this route
        route_segments = []
        for i in range(len(route_nodes) - 1):
            from_node = route_nodes[i]
            to_node = route_nodes[i + 1]
            travel_time = distance_matrix[from_node][to_node]
            vehicle_cost += travel_time
            route_segments.append(f"{from_node}->{to_node}: {travel_time:.2f}")

        vehicle_costs[vehicle_id] = vehicle_cost
        total_cost += vehicle_cost

        # Print vehicle route details
        print(f"\nVehicle {vehicle_id}: Requests {request_ids}")
        print(f"  Route: {' -> '.join(map(str, route_nodes))}")
        print(f"  Segments: {', '.join(route_segments)}")
        print(f"  Vehicle Cost: {vehicle_cost:.2f} minutes")

    print("\n" + "-"*80)
    print(f"TOTAL ROUTING COST: {total_cost:.2f} minutes")
    print("="*80)

    return {
        'total_cost': total_cost,
        'vehicle_costs': vehicle_costs,
        'num_vehicles_used': len([v for v in vehicle_costs.values() if v > 0])
    }


def evaluate_dummy_agent():
    """
    Run the dummy agent and evaluate its performance.
    """
    print("="*80)
    print("EVALUATION: Dummy Agent Performance")
    print("="*80)

    # Initialize and run dummy agent
    import random
    random.seed(42)  # Same seed as dummy.py for consistency

    agent = DummyAgent(num_vehicles=10)

    # Load data
    data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_sampling'))
    distance_matrix_path = os.path.join(data_dir, 'distance_matrix.npy')
    requests_csv_path = os.path.join(data_dir, 'sampled_requests_with_coords.csv')

    agent.load_data(distance_matrix_path, requests_csv_path)

    # Run assignment
    assignments, unassigned = agent.run()

    # Calculate routing cost
    cost_results = calculate_routing_cost(
        assignments,
        agent.distance_matrix,
        num_vehicles=agent.num_vehicles
    )

    # Summary
    print("\n" + "="*80)
    print("EVALUATION SUMMARY")
    print("="*80)
    print(f"Total Requests: {len(agent.requests_data)}")
    print(f"Assigned Requests: {len(agent.requests_data) - len(unassigned)}")
    print(f"Unassigned Requests: {len(unassigned)}")
    print(f"Vehicles Used: {cost_results['num_vehicles_used']}")
    print(f"Total Routing Cost: {cost_results['total_cost']:.2f} minutes")

    if unassigned:
        print(f"\nUnassigned Request IDs: {unassigned}")
        print("Note: Unassigned requests are not included in routing cost")

    # Compare with OR-Tools solution if available
    try:
        routing_solution_path = os.path.join(data_dir, 'routing_solution.txt')
        with open(routing_solution_path, 'r') as f:
            content = f.read()
            # Extract OR-Tools cost
            import re
            match = re.search(r'Total Cost: ([\d.]+)', content)
            if match:
                ortools_cost = float(match.group(1))
                print(f"\n--- Comparison with OR-Tools ---")
                print(f"Dummy Agent Cost: {cost_results['total_cost']:.2f} minutes")
                print(f"OR-Tools Cost: {ortools_cost:.2f} minutes")
                gap = ((cost_results['total_cost'] - ortools_cost) / ortools_cost) * 100
                print(f"Gap: {gap:+.2f}%")
    except Exception as e:
        print(f"\nNote: Could not compare with OR-Tools solution: {e}")

    # Save evaluation results
    output_file = os.path.join(data_dir, 'dummy_agent_evaluation.txt')
    with open(output_file, 'w') as f:
        f.write("Dummy Agent Evaluation Results\n")
        f.write("="*80 + "\n\n")
        f.write(f"Total Requests: {len(agent.requests_data)}\n")
        f.write(f"Assigned Requests: {len(agent.requests_data) - len(unassigned)}\n")
        f.write(f"Unassigned Requests: {len(unassigned)}\n")
        f.write(f"Vehicles Used: {cost_results['num_vehicles_used']}\n")
        f.write(f"Total Routing Cost: {cost_results['total_cost']:.2f} minutes\n\n")

        f.write("Vehicle Assignments and Costs:\n")
        f.write("-"*80 + "\n")
        for vehicle_id in sorted(assignments.keys()):
            requests = assignments[vehicle_id]
            cost = cost_results['vehicle_costs'][vehicle_id]
            f.write(f"Vehicle {vehicle_id}: Requests {requests}, Cost: {cost:.2f} minutes\n")

        if unassigned:
            f.write(f"\nUnassigned Request IDs: {unassigned}\n")

    print(f"\nEvaluation results saved to: {output_file}")

    return cost_results


def main():
    """Main function to evaluate dummy agent."""
    evaluate_dummy_agent()


if __name__ == "__main__":
    main()
