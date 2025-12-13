"""
Event Logger for Green Agent Evaluation

Comprehensive logging system that tracks all events during evaluation:
- Vehicle initialization
- Request arrivals
- Parsing decisions
- Routing decisions
- Vehicle movements
- Trip completions
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass, asdict


@dataclass
class LogEvent:
    """Base class for log events."""
    timestamp: datetime
    event_type: str
    event_data: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'event_type': self.event_type,
            'event_data': self.event_data
        }


class EventLogger:
    """
    Comprehensive event logger for the evaluation system.

    Logs all events to both console and file for debugging and analysis.
    """

    def __init__(
        self,
        log_file_path: Optional[str] = None,
        console_level: int = logging.INFO,
        file_level: int = logging.DEBUG,
        enable_json_log: bool = True
    ):
        """
        Initialize event logger.

        Args:
            log_file_path: Path to log file (None = don't log to file)
            console_level: Logging level for console output
            file_level: Logging level for file output
            enable_json_log: Whether to also create a JSON event log
        """
        self.log_file_path = log_file_path
        self.enable_json_log = enable_json_log
        self.json_events: List[LogEvent] = []

        # Create logger
        self.logger = logging.getLogger('GreenAgent')
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False

        # Remove existing handlers
        self.logger.handlers.clear()

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(console_level)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)

        # File handler
        if log_file_path:
            log_path = Path(log_file_path)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            file_handler = logging.FileHandler(log_file_path, mode='w')
            file_handler.setLevel(file_level)
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)

        self.logger.info(f"EventLogger initialized (log_file={log_file_path})")

    def log_event(self, event_type: str, event_data: Dict[str, Any], level: int = logging.INFO):
        """
        Log an event.

        Args:
            event_type: Type of event (e.g., 'VEHICLE_INIT', 'REQUEST_ARRIVAL')
            event_data: Event data dictionary
            level: Logging level
        """
        # Create log event
        event = LogEvent(
            timestamp=datetime.now(),
            event_type=event_type,
            event_data=event_data
        )

        # Log to console/file
        self.logger.log(level, f"[{event_type}] {json.dumps(event_data, default=str)}")

        # Store for JSON export
        if self.enable_json_log:
            self.json_events.append(event)

    # =========================================================================
    # Vehicle Events
    # =========================================================================

    def log_vehicle_initialization(
        self,
        vehicle_id: str,
        location: Dict[str, Any],
        wheelchair_accessible: bool
    ):
        """Log vehicle initialization."""
        self.log_event('VEHICLE_INIT', {
            'vehicle_id': vehicle_id,
            'location': location,
            'wheelchair_accessible': wheelchair_accessible
        })

    def log_vehicle_assignment(
        self,
        vehicle_id: str,
        request_id: str,
        current_location: Dict[str, Any],
        pickup_location: Dict[str, Any],
        estimated_pickup_distance: float,
        estimated_pickup_time: float
    ):
        """Log vehicle assignment to request."""
        self.log_event('VEHICLE_ASSIGNMENT', {
            'vehicle_id': vehicle_id,
            'request_id': request_id,
            'current_location': current_location,
            'pickup_location': pickup_location,
            'estimated_pickup_distance_miles': estimated_pickup_distance,
            'estimated_pickup_time_minutes': estimated_pickup_time
        })

    def log_vehicle_movement(
        self,
        vehicle_id: str,
        from_location: Dict[str, Any],
        to_location: Dict[str, Any],
        distance_miles: float,
        duration_minutes: float,
        movement_type: str  # 'DEADHEAD', 'ON_TRIP'
    ):
        """Log vehicle movement."""
        self.log_event('VEHICLE_MOVEMENT', {
            'vehicle_id': vehicle_id,
            'from_location': from_location,
            'to_location': to_location,
            'distance_miles': distance_miles,
            'duration_minutes': duration_minutes,
            'movement_type': movement_type
        })

    def log_trip_completion(
        self,
        vehicle_id: str,
        request_id: str,
        trip_distance: float,
        trip_time: float,
        fare: float,
        deadhead_miles: float
    ):
        """Log trip completion."""
        self.log_event('TRIP_COMPLETE', {
            'vehicle_id': vehicle_id,
            'request_id': request_id,
            'trip_distance_miles': trip_distance,
            'trip_time_minutes': trip_time,
            'fare': fare,
            'deadhead_miles': deadhead_miles,
            'net_revenue': fare - (deadhead_miles * 0.50)
        })

    # =========================================================================
    # Request Events
    # =========================================================================

    def log_request_arrival(
        self,
        request_id: str,
        request_time: datetime,
        natural_language_text: str,
        ground_truth: Optional[Dict[str, Any]] = None
    ):
        """Log new request arrival."""
        self.log_event('REQUEST_ARRIVAL', {
            'request_id': request_id,
            'request_time': request_time.isoformat(),
            'natural_language_text': natural_language_text,
            'has_ground_truth': ground_truth is not None
        })

    def log_parsing_result(
        self,
        request_id: str,
        parsed_request: Dict[str, Any],
        parsing_time_ms: float,
        parsing_accuracy: Optional[Dict[str, bool]] = None
    ):
        """Log request parsing result."""
        self.log_event('REQUEST_PARSED', {
            'request_id': request_id,
            'parsed_request': parsed_request,
            'parsing_time_ms': parsing_time_ms,
            'parsing_accuracy': parsing_accuracy
        })

    def log_routing_decision(
        self,
        request_id: str,
        routing_decision: Dict[str, Any],
        decision_time_ms: float,
        available_vehicles_count: int
    ):
        """Log routing decision."""
        self.log_event('ROUTING_DECISION', {
            'request_id': request_id,
            'routing_decision': routing_decision,
            'decision_time_ms': decision_time_ms,
            'available_vehicles_count': available_vehicles_count
        })

    # =========================================================================
    # Evaluation Events
    # =========================================================================

    def log_evaluation_start(
        self,
        agent_name: str,
        num_requests: int,
        num_vehicles: int,
        start_time: datetime
    ):
        """Log evaluation start."""
        self.log_event('EVALUATION_START', {
            'agent_name': agent_name,
            'num_requests': num_requests,
            'num_vehicles': num_vehicles,
            'start_time': start_time.isoformat()
        }, level=logging.INFO)

    def log_evaluation_end(
        self,
        agent_name: str,
        summary: Dict[str, Any],
        end_time: datetime
    ):
        """Log evaluation end."""
        self.log_event('EVALUATION_END', {
            'agent_name': agent_name,
            'summary': summary,
            'end_time': end_time.isoformat()
        }, level=logging.INFO)

    def log_error(
        self,
        error_type: str,
        error_message: str,
        context: Optional[Dict[str, Any]] = None
    ):
        """Log error."""
        self.log_event('ERROR', {
            'error_type': error_type,
            'error_message': error_message,
            'context': context or {}
        }, level=logging.ERROR)

    # =========================================================================
    # Utilities
    # =========================================================================

    def save_json_log(self, output_path: str):
        """
        Save JSON event log to file.

        Args:
            output_path: Path to save JSON log
        """
        if not self.enable_json_log:
            self.logger.warning("JSON logging is disabled")
            return

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        events_dict = [event.to_dict() for event in self.json_events]

        with open(output_file, 'w') as f:
            json.dump(events_dict, f, indent=2, default=str)

        self.logger.info(f"Saved {len(events_dict)} events to {output_path}")

    def get_events_by_type(self, event_type: str) -> List[LogEvent]:
        """Get all events of a specific type."""
        return [e for e in self.json_events if e.event_type == event_type]

    def get_events_for_request(self, request_id: str) -> List[LogEvent]:
        """Get all events related to a specific request."""
        return [
            e for e in self.json_events
            if e.event_data.get('request_id') == request_id
        ]

    def get_events_for_vehicle(self, vehicle_id: str) -> List[LogEvent]:
        """Get all events related to a specific vehicle."""
        return [
            e for e in self.json_events
            if e.event_data.get('vehicle_id') == vehicle_id
        ]

    def get_statistics(self) -> Dict[str, Any]:
        """Get logging statistics."""
        event_counts = {}
        for event in self.json_events:
            event_type = event.event_type
            event_counts[event_type] = event_counts.get(event_type, 0) + 1

        return {
            'total_events': len(self.json_events),
            'event_counts': event_counts,
            'first_event': self.json_events[0].timestamp.isoformat() if self.json_events else None,
            'last_event': self.json_events[-1].timestamp.isoformat() if self.json_events else None
        }

    def clear(self):
        """Clear all logged events."""
        self.json_events.clear()
        self.logger.info("Event log cleared")

    def __repr__(self) -> str:
        return f"EventLogger(events={len(self.json_events)}, file={self.log_file_path})"
