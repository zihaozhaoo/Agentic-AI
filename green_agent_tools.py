"""
Green Agent Tools for Ride-Hailing Evaluation

These tools are called by the green agent to perform evaluation tasks.
"""

import sys
import os
from pathlib import Path
from typing import Dict, Any, List
import json

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from request_simulation import RequestSimulator
from environment import GreenAgentEnvironment
from white_agent import NaturalLanguageRequest, StructuredRequest
from vehicle_system import VehicleDatabase
from evaluation import Evaluator
from utils import EventLogger


def initialize_evaluation_environment(
    num_vehicles: int = 100,
    parquet_path: str = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Initialize the evaluation environment with vehicle fleet and request simulator.

    Args:
        num_vehicles: Number of vehicles to initialize
        parquet_path: Path to NYC trip data parquet file
        **kwargs: Additional configuration

    Returns:
        Status and environment info
    """
    try:
        project_root = Path(__file__).parent
        taxi_zone_lookup = str(project_root / "taxi_zone_lookup.csv")

        if parquet_path is None:
            parquet_path = str(project_root / "fhvhv_tripdata_2025-01.parquet")

        # Initialize request simulator
        request_simulator = RequestSimulator(
            taxi_zone_lookup_path=taxi_zone_lookup,
            template_ratio=1.0,
        )

        # Initialize environment
        environment = GreenAgentEnvironment(
            request_simulator=request_simulator,
            logger=EventLogger()
        )

        # Initialize vehicles
        environment.initialize_vehicles(
            num_vehicles=num_vehicles,
            wheelchair_accessible_ratio=0.1,
            sample_parquet_path=parquet_path,
            sample_size=1000
        )

        return {
            "status": "success",
            "message": f"Initialized environment with {num_vehicles} vehicles",
            "fleet_stats": environment.vehicle_database.get_fleet_statistics()
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to initialize environment: {str(e)}"
        }


def generate_ride_requests(
    num_requests: int = 10,
    parquet_path: str = None,
    augment_location: bool = False,
    **kwargs
) -> Dict[str, Any]:
    """
    Generate natural language ride requests from trip data.

    Args:
        num_requests: Number of requests to generate
        parquet_path: Path to NYC trip data
        augment_location: Whether to use Google Maps API for exact coordinates

    Returns:
        Generated requests
    """
    try:
        project_root = Path(__file__).parent
        taxi_zone_lookup = str(project_root / "taxi_zone_lookup.csv")

        if parquet_path is None:
            parquet_path = str(project_root / "fhvhv_tripdata_2025-01.parquet")

        # Initialize request simulator
        request_simulator = RequestSimulator(
            taxi_zone_lookup_path=taxi_zone_lookup,
            template_ratio=1.0,
        )

        # Initialize environment
        environment = GreenAgentEnvironment(
            request_simulator=request_simulator
        )

        # Generate requests
        requests = environment.generate_requests_from_data(
            parquet_path=parquet_path,
            n_requests=num_requests,
            augment_location=augment_location
        )

        # Format for output (truncate full data)
        request_summaries = []
        for req in requests[:5]:  # Show first 5
            request_summaries.append({
                "trip_id": req.get("trip_id"),
                "request": req.get("request", "")[:100] + "...",
                "pickup_zone": req.get("pickup_zone"),
                "dropoff_zone": req.get("dropoff_zone"),
                "request_time": str(req.get("request_time"))
            })

        return {
            "status": "success",
            "message": f"Generated {len(requests)} requests",
            "total_requests": len(requests),
            "sample_requests": request_summaries
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to generate requests: {str(e)}"
        }


def evaluate_white_agent_parsing(
    parsed_request: Dict[str, Any],
    ground_truth: Dict[str, Any],
    **kwargs
) -> Dict[str, Any]:
    """
    Evaluate white agent's parsing accuracy.

    Args:
        parsed_request: White agent's parsed request
        ground_truth: Ground truth structured request

    Returns:
        Parsing evaluation scores
    """
    try:
        evaluator = Evaluator()

        # Convert dicts to StructuredRequest objects if needed
        # This is simplified - in reality you'd need proper conversion

        scores = {
            "origin_zone_match": parsed_request.get("origin", {}).get("zone_id") == ground_truth.get("origin", {}).get("zone_id"),
            "destination_zone_match": parsed_request.get("destination", {}).get("zone_id") == ground_truth.get("destination", {}).get("zone_id"),
            "time_constraint_match": parsed_request.get("pickup_time") == ground_truth.get("pickup_time"),
            "passenger_count_match": parsed_request.get("passenger_count") == ground_truth.get("passenger_count"),
            "special_requirements_match": parsed_request.get("wheelchair_accessible") == ground_truth.get("wheelchair_accessible")
        }

        accuracy = sum(scores.values()) / len(scores)

        return {
            "status": "success",
            "accuracy": accuracy,
            "detailed_scores": scores
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to evaluate parsing: {str(e)}"
        }


def evaluate_routing_decision(
    routing_decision: Dict[str, Any],
    vehicle_database: Dict[str, Any],
    **kwargs
) -> Dict[str, Any]:
    """
    Evaluate white agent's routing decision.

    Args:
        routing_decision: White agent's vehicle assignment and routing plan
        vehicle_database: Current vehicle fleet state

    Returns:
        Routing evaluation metrics
    """
    try:
        # Calculate metrics
        metrics = {
            "vehicle_assigned": routing_decision.get("vehicle_id") is not None,
            "estimated_pickup_time": routing_decision.get("estimated_pickup_time"),
            "estimated_pickup_distance": routing_decision.get("estimated_pickup_distance"),
            "valid_assignment": True  # Would validate against actual fleet
        }

        return {
            "status": "success",
            "metrics": metrics
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to evaluate routing: {str(e)}"
        }


def calculate_performance_metrics(
    completed_requests: List[Dict[str, Any]],
    **kwargs
) -> Dict[str, Any]:
    """
    Calculate comprehensive performance metrics for evaluation period.

    Args:
        completed_requests: List of processed requests with outcomes

    Returns:
        Comprehensive performance metrics
    """
    try:
        total_requests = len(completed_requests)
        successful = sum(1 for r in completed_requests if r.get("success"))

        # Calculate revenue and costs (simplified)
        total_revenue = 0
        total_idle_cost = 0
        total_deadhead_miles = 0

        for req in completed_requests:
            if req.get("success"):
                trip_result = req.get("trip_result", {})
                total_revenue += trip_result.get("fare", 0)
                total_idle_cost += trip_result.get("deadhead_miles", 0) * 0.5  # $0.5 per mile
                total_deadhead_miles += trip_result.get("deadhead_miles", 0)

        net_revenue = total_revenue - total_idle_cost

        metrics = {
            "total_requests": total_requests,
            "successful_requests": successful,
            "success_rate": successful / total_requests if total_requests > 0 else 0,
            "total_revenue": total_revenue,
            "total_idle_cost": total_idle_cost,
            "net_revenue": net_revenue,
            "total_deadhead_miles": total_deadhead_miles,
            "deadhead_ratio": total_deadhead_miles / (total_deadhead_miles + 100) if total_deadhead_miles > 0 else 0,  # Simplified
            "overall_score": (net_revenue / 1000) if total_revenue > 0 else 0  # Normalized score
        }

        return {
            "status": "success",
            "metrics": metrics
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to calculate metrics: {str(e)}"
        }


# Export tools for AgentBeats
TOOLS = [
    initialize_evaluation_environment,
    generate_ride_requests,
    evaluate_white_agent_parsing,
    evaluate_routing_decision,
    calculate_performance_metrics
]
