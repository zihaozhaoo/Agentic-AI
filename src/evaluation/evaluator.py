"""
Evaluation System

Evaluates white agent performance on:
1. Natural language parsing accuracy
2. Routing decision optimality
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import math

from white_agent.data_structures import (
    StructuredRequest,
    RoutingDecision,
    NaturalLanguageRequest,
    Location
)
from vehicle_system import VehicleSimulator, VehicleDatabase


@dataclass
class ParsingMetrics:
    """Metrics for parsing accuracy evaluation."""
    total_requests: int = 0
    correct_origin_zone: int = 0
    correct_destination_zone: int = 0
    correct_time_constraint: int = 0
    correct_special_requirements: int = 0

    # Distance errors (for location accuracy)
    origin_distance_errors: List[float] = field(default_factory=list)
    destination_distance_errors: List[float] = field(default_factory=list)

    @property
    def origin_zone_accuracy(self) -> float:
        """Origin zone identification accuracy."""
        return self.correct_origin_zone / self.total_requests if self.total_requests > 0 else 0.0

    @property
    def destination_zone_accuracy(self) -> float:
        """Destination zone identification accuracy."""
        return self.correct_destination_zone / self.total_requests if self.total_requests > 0 else 0.0

    @property
    def time_constraint_accuracy(self) -> float:
        """Time constraint parsing accuracy."""
        return self.correct_time_constraint / self.total_requests if self.total_requests > 0 else 0.0

    @property
    def special_requirements_accuracy(self) -> float:
        """Special requirements parsing accuracy."""
        return self.correct_special_requirements / self.total_requests if self.total_requests > 0 else 0.0

    @property
    def mean_origin_error_miles(self) -> float:
        """Mean origin location error in miles."""
        return sum(self.origin_distance_errors) / len(self.origin_distance_errors) if self.origin_distance_errors else 0.0

    @property
    def mean_destination_error_miles(self) -> float:
        """Mean destination location error in miles."""
        return sum(self.destination_distance_errors) / len(self.destination_distance_errors) if self.destination_distance_errors else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'total_requests': self.total_requests,
            'origin_zone_accuracy': self.origin_zone_accuracy,
            'destination_zone_accuracy': self.destination_zone_accuracy,
            'time_constraint_accuracy': self.time_constraint_accuracy,
            'special_requirements_accuracy': self.special_requirements_accuracy,
            'mean_origin_error_miles': self.mean_origin_error_miles,
            'mean_destination_error_miles': self.mean_destination_error_miles,
        }


@dataclass
class RoutingMetrics:
    """Metrics for routing decision evaluation."""
    total_requests: int = 0
    total_revenue: float = 0.0
    total_trip_miles: float = 0.0
    total_deadhead_miles: float = 0.0
    total_idle_cost: float = 0.0

    # Response time metrics
    pickup_times: List[float] = field(default_factory=list)
    trip_times: List[float] = field(default_factory=list)

    # Optimality metrics
    deadhead_miles_by_request: List[float] = field(default_factory=list)

    @property
    def net_revenue(self) -> float:
        """Net revenue = total revenue - idle cost."""
        return self.total_revenue - self.total_idle_cost

    @property
    def deadhead_ratio(self) -> float:
        """Ratio of deadhead miles to total miles."""
        total_miles = self.total_trip_miles + self.total_deadhead_miles
        return self.total_deadhead_miles / total_miles if total_miles > 0 else 0.0

    @property
    def average_pickup_time(self) -> float:
        """Average pickup time in minutes."""
        return sum(self.pickup_times) / len(self.pickup_times) if self.pickup_times else 0.0

    @property
    def average_trip_time(self) -> float:
        """Average trip time in minutes."""
        return sum(self.trip_times) / len(self.trip_times) if self.trip_times else 0.0

    @property
    def revenue_per_mile(self) -> float:
        """Revenue per mile driven."""
        total_miles = self.total_trip_miles + self.total_deadhead_miles
        return self.total_revenue / total_miles if total_miles > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'total_requests': self.total_requests,
            'total_revenue': self.total_revenue,
            'total_idle_cost': self.total_idle_cost,
            'net_revenue': self.net_revenue,
            'total_trip_miles': self.total_trip_miles,
            'total_deadhead_miles': self.total_deadhead_miles,
            'deadhead_ratio': self.deadhead_ratio,
            'average_pickup_time_minutes': self.average_pickup_time,
            'average_trip_time_minutes': self.average_trip_time,
            'revenue_per_mile': self.revenue_per_mile,
        }


class Evaluator:
    """
    Evaluates white agent performance.

    Evaluates two main aspects:
    1. Parsing accuracy: How well the agent extracts structured info from NL
    2. Routing optimality: How efficiently the agent assigns vehicles
    """

    def __init__(
        self,
        idle_cost_per_mile: float = 0.50,
        unmet_demand_penalty: float = 50.0
    ):
        """
        Initialize evaluator.

        Args:
            idle_cost_per_mile: Cost per deadhead mile
            unmet_demand_penalty: Penalty for unmet demand
        """
        self.idle_cost_per_mile = idle_cost_per_mile
        self.unmet_demand_penalty = unmet_demand_penalty

        self.parsing_metrics = ParsingMetrics()
        self.routing_metrics = RoutingMetrics()

        # Store evaluations for detailed analysis
        self.request_evaluations: List[Dict[str, Any]] = []
        # Per-request scores for overall aggregation
        self.request_scores: List[float] = []

    def evaluate_parsing(
        self,
        nl_request: NaturalLanguageRequest,
        parsed_request: StructuredRequest
    ) -> Dict[str, Any]:
        """
        Evaluate parsing accuracy for a single request.

        Args:
            nl_request: Original natural language request with ground truth
            parsed_request: Parsed request from white agent

        Returns:
            Dictionary with parsing evaluation results
        """
        if not nl_request.ground_truth:
            return {'error': 'No ground truth available'}

        ground_truth = nl_request.ground_truth

        # Evaluate zone identification
        origin_zone_correct = (
            parsed_request.origin.zone_id == ground_truth.origin.zone_id
            if parsed_request.origin.zone_id and ground_truth.origin.zone_id
            else False
        )

        destination_zone_correct = (
            parsed_request.destination.zone_id == ground_truth.destination.zone_id
            if parsed_request.destination.zone_id and ground_truth.destination.zone_id
            else False
        )

        # Calculate location distance errors
        origin_error = self._calculate_distance(
            parsed_request.origin.latitude,
            parsed_request.origin.longitude,
            ground_truth.origin.latitude,
            ground_truth.origin.longitude
        )

        destination_error = self._calculate_distance(
            parsed_request.destination.latitude,
            parsed_request.destination.longitude,
            ground_truth.destination.latitude,
            ground_truth.destination.longitude
        )

        # Evaluate time constraints
        time_constraint_correct = (
            parsed_request.has_arrival_constraint == ground_truth.has_arrival_constraint
        )

        # Evaluate special requirements
        special_requirements_correct = (
            parsed_request.wheelchair_accessible == ground_truth.wheelchair_accessible and
            parsed_request.shared_ride_ok == ground_truth.shared_ride_ok and
            parsed_request.passenger_count == ground_truth.passenger_count
        )

        # Update metrics
        self.parsing_metrics.total_requests += 1
        if origin_zone_correct:
            self.parsing_metrics.correct_origin_zone += 1
        if destination_zone_correct:
            self.parsing_metrics.correct_destination_zone += 1
        if time_constraint_correct:
            self.parsing_metrics.correct_time_constraint += 1
        if special_requirements_correct:
            self.parsing_metrics.correct_special_requirements += 1

        self.parsing_metrics.origin_distance_errors.append(origin_error)
        self.parsing_metrics.destination_distance_errors.append(destination_error)

        return {
            'origin_zone_correct': origin_zone_correct,
            'destination_zone_correct': destination_zone_correct,
            'origin_distance_error_miles': origin_error,
            'destination_distance_error_miles': destination_error,
            'time_constraint_correct': time_constraint_correct,
            'special_requirements_correct': special_requirements_correct,
        }

    def evaluate_routing(
        self,
        routing_decision: RoutingDecision,
        trip_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluate routing decision for a single request.

        Args:
            routing_decision: Routing decision from white agent
            trip_result: Actual trip execution results from simulator

        Returns:
            Dictionary with routing evaluation results
        """
        # Extract trip metrics
        deadhead_miles = trip_result.get('deadhead_miles', 0.0)
        trip_miles = trip_result.get('trip_distance', 0.0)
        fare = trip_result.get('fare', 0.0)
        pickup_time = trip_result.get('actual_pickup_time', 0.0)
        trip_time = trip_result.get('trip_time', 0.0)

        # Calculate idle cost
        idle_cost = deadhead_miles * self.idle_cost_per_mile

        # Update metrics
        self.routing_metrics.total_requests += 1
        self.routing_metrics.total_revenue += fare
        self.routing_metrics.total_trip_miles += trip_miles
        self.routing_metrics.total_deadhead_miles += deadhead_miles
        self.routing_metrics.total_idle_cost += idle_cost
        self.routing_metrics.pickup_times.append(pickup_time)
        self.routing_metrics.trip_times.append(trip_time)
        self.routing_metrics.deadhead_miles_by_request.append(deadhead_miles)

        # Calculate net revenue for this request
        net_revenue = fare - idle_cost

        return {
            'deadhead_miles': deadhead_miles,
            'trip_miles': trip_miles,
            'fare': fare,
            'idle_cost': idle_cost,
            'net_revenue': net_revenue,
            'pickup_time_minutes': pickup_time,
            'trip_time_minutes': trip_time,
        }

    def evaluate_request(
        self,
        nl_request: NaturalLanguageRequest,
        parsed_request: StructuredRequest,
        routing_decision: RoutingDecision,
        trip_result: Optional[Dict[str, Any]] = None
    ):
        """
        Evaluate a complete request (parsing + routing).

        Args:
            nl_request: Original natural language request
            parsed_request: Parsed request from white agent
            routing_decision: Routing decision from white agent
            trip_result: Trip execution results (if available)
        """
        # Evaluate parsing
        parsing_eval = self.evaluate_parsing(nl_request, parsed_request)

        # Evaluate routing (if trip result available)
        routing_eval = {}
        if trip_result:
            routing_eval = self.evaluate_routing(routing_decision, trip_result)

        # Store evaluation
        self.request_evaluations.append({
            'request_id': nl_request.request_id,
            'parsing': parsing_eval,
            'routing': routing_eval,
        })

        # Custom per-request score: parse correctness * trip_share_of_total_miles
        parse_ok = parsing_eval.get('origin_zone_correct') and parsing_eval.get('destination_zone_correct')
        trip_miles = (trip_result or {}).get('trip_distance', 0.0)
        deadhead_miles = (trip_result or {}).get('deadhead_miles', 0.0)
        denom = trip_miles + deadhead_miles
        share = (trip_miles / denom) if denom > 0 else 0.0
        score = (1.0 if parse_ok else 0.0) * share
        self.request_scores.append(score)

    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary of all evaluations.

        Returns:
            Dictionary with complete evaluation summary
        """
        return {
            'parsing_metrics': self.parsing_metrics.to_dict(),
            'routing_metrics': self.routing_metrics.to_dict(),
            'total_requests_evaluated': len(self.request_evaluations),
            'overall_score': self._calculate_overall_score(),
        }

    def _calculate_overall_score(self) -> float:
        """
        Calculate overall score as the mean of per-request scores:
        score_i = parse_correct * trip_miles / (trip_miles + deadhead_miles)

        Returns:
            Overall score (0-100 scaled)
        """
        if not self.request_scores:
            return 0.0
        return (sum(self.request_scores) / len(self.request_scores)) * 100.0

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
            lat1, lon1: First point
            lat2, lon2: Second point

        Returns:
            Distance in miles
        """
        R = 3959.0  # Earth radius in miles

        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)

        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
        c = 2 * math.asin(math.sqrt(a))

        return R * c

    def reset(self):
        """Reset all metrics."""
        self.parsing_metrics = ParsingMetrics()
        self.routing_metrics = RoutingMetrics()
        self.request_evaluations.clear()
        self.request_scores.clear()

    def __repr__(self) -> str:
        summary = self.get_summary()
        return (f"Evaluator(requests={summary['total_requests_evaluated']}, "
                f"score={summary['overall_score']:.2f})")
