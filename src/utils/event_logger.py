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
        deadhead_miles: float,
        pickup_location: Optional[Dict[str, Any]] = None,
        dropoff_location: Optional[Dict[str, Any]] = None,
        pickup_location_ground_truth: Optional[Dict[str, Any]] = None,
        dropoff_location_ground_truth: Optional[Dict[str, Any]] = None
    ):
        """Log trip completion (optionally with coordinates for mapping)."""
        self.log_event('TRIP_COMPLETE', {
            'vehicle_id': vehicle_id,
            'request_id': request_id,
            'trip_distance_miles': trip_distance,
            'trip_time_minutes': trip_time,
            'fare': fare,
            'deadhead_miles': deadhead_miles,
            'net_revenue': fare - (deadhead_miles * 0.50),
            'pickup_location_parsed': pickup_location,
            'dropoff_location_parsed': dropoff_location,
            'pickup_location_ground_truth': pickup_location_ground_truth,
            'dropoff_location_ground_truth': dropoff_location_ground_truth,
            # Keep backward compatibility
            'pickup_location': pickup_location,
            'dropoff_location': dropoff_location
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
        event_data = {
            'request_id': request_id,
            'request_time': request_time.isoformat(),
            'natural_language_text': natural_language_text,
            'has_ground_truth': ground_truth is not None
        }

        # Include full ground truth data if available
        if ground_truth:
            event_data['ground_truth'] = ground_truth

        self.log_event('REQUEST_ARRIVAL', event_data)

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

    def export_trajectories_json(self, output_path: str):
        """
        Export simplified trajectories for mapping and animation.

        The output groups vehicle assignments and trip completions into
        per-request trajectories with coordinates for deadhead and on-trip legs.
        """
        assignments = {}
        trips = []

        for event in self.json_events:
            if event.event_type == 'VEHICLE_ASSIGNMENT':
                data = event.event_data
                rid = data.get('request_id')
                assignments[rid] = {
                    'vehicle_id': data.get('vehicle_id'),
                    'vehicle_start': data.get('current_location'),
                    'pickup_location': data.get('pickup_location'),
                    'estimated_pickup_distance_miles': data.get('estimated_pickup_distance_miles'),
                    'estimated_pickup_time_minutes': data.get('estimated_pickup_time_minutes')
                }
            elif event.event_type == 'TRIP_COMPLETE':
                trips.append(event.event_data)

        trajectories = []
        for trip in trips:
            rid = trip.get('request_id')
            assignment = assignments.get(rid, {})

            start_loc = assignment.get('vehicle_start')
            pickup_loc = assignment.get('pickup_location') or trip.get('pickup_location')
            dropoff_loc = trip.get('dropoff_location')

            trajectories.append({
                'request_id': rid,
                'vehicle_id': assignment.get('vehicle_id') or trip.get('vehicle_id'),
                'vehicle_start': start_loc,
                'pickup': pickup_loc,
                'dropoff': dropoff_loc,
                'deadhead_distance_miles': trip.get('deadhead_miles'),
                'trip_distance_miles': trip.get('trip_distance_miles'),
                'fare': trip.get('fare'),
                'net_revenue': trip.get('net_revenue')
            })

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w') as f:
            json.dump({'trajectories': trajectories}, f, indent=2)

        self.logger.info(f"Exported {len(trajectories)} trajectories to {output_path}")

    def export_map_html(
        self,
        output_path: str,
        center_lat: float = 40.7589,
        center_lon: float = -73.9851,
        zoom: int = 11
    ):
        """
        Render an interactive HTML map that focuses on per-vehicle animation.

        This version keeps animation logic simple and reliable:
        - One request plays at a time (vehicle_start -> pickup -> dropoff)
        - "Play" starts/resumes sequential playback
        - "Next" instantly completes the current leg/request and moves on
        - Vehicle status list updates live (idle / to_pickup / occupied)
        """
        # Build trajectory data inline with durations and status cues
        assignments: Dict[str, Dict[str, Any]] = {}
        trips: List[Dict[str, Any]] = []

        for event in self.json_events:
            if event.event_type == 'VEHICLE_ASSIGNMENT':
                data = event.event_data
                rid = data.get('request_id')
                assignments[rid] = {
                    'vehicle_id': data.get('vehicle_id'),
                    'vehicle_start': data.get('current_location'),
                    'pickup': data.get('pickup_location'),
                    'eta_minutes': data.get('estimated_pickup_time_minutes'),
                    'deadhead_distance_miles': data.get('estimated_pickup_distance_miles'),
                }
            elif event.event_type == 'TRIP_COMPLETE':
                trips.append(event.event_data)

        trajectories = []
        for trip in trips:
            rid = trip.get('request_id')
            assignment = assignments.get(rid, {})

            deadhead_minutes = assignment.get('eta_minutes')
            if deadhead_minutes is None:
                dist = assignment.get('deadhead_distance_miles') or 2.0
                deadhead_minutes = max(4.0, (dist / 18.0) * 60.0)  # ~18 mph city speed

            trip_minutes = trip.get('trip_time_minutes')
            if trip_minutes is None:
                dist = trip.get('trip_distance_miles') or 2.5
                trip_minutes = max(6.0, (dist / 18.0) * 60.0)

            trajectories.append({
                'request_id': rid,
                'vehicle_id': assignment.get('vehicle_id') or trip.get('vehicle_id'),
                'vehicle_start': assignment.get('vehicle_start'),
                'pickup': assignment.get('pickup') or trip.get('pickup_location'),
                'dropoff': trip.get('dropoff_location'),
                'deadhead_minutes': deadhead_minutes,
                'trip_minutes': trip_minutes,
                'deadhead_miles': trip.get('deadhead_miles'),
                'trip_miles': trip.get('trip_distance_miles'),
                'fare': trip.get('fare'),
            })

        html_template = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Agentic-AI Trajectories</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <style>
    html, body, #map {{ height: 100%; margin: 0; padding: 0; }}
    .controls {{ position: absolute; top: 10px; left: 10px; z-index: 1000; background: white; padding: 10px; border-radius: 6px; box-shadow: 0 1px 4px rgba(0,0,0,0.3); width: 260px; }}
    .legend-item {{ display: flex; align-items: center; gap: 6px; font-size: 12px; margin-bottom: 4px; }}
    .legend-swatch {{ width: 14px; height: 6px; border-radius: 3px; }}
    .status-list {{ max-height: 220px; overflow-y: auto; margin-top: 8px; padding: 6px; border: 1px solid #ddd; border-radius: 4px; background: #fafafa; }}
    .status-entry {{ display: flex; align-items: center; gap: 6px; font-size: 12px; padding: 2px 0; }}
    .totals {{ font-size: 12px; margin-top: 6px; }}
    button {{ margin-right: 6px; }}
  </style>
</head>
<body>
  <div id="map"></div>
  <div class="controls">
    <button id="playBtn">Play</button>
    <button id="nextBtn">Next</button>
    <button id="resetBtn">Reset</button>
    <div style="margin-top:6px; font-size: 12px;"><strong>Status:</strong> <span id="status">Idle</span></div>
    <div style="margin-top:8px;">
      <div class="legend-item"><span class="legend-swatch" style="background:#ff3b30"></span>Deadhead (vehicle -> pickup)</div>
      <div class="legend-item"><span class="legend-swatch" style="background:#34c759"></span>On trip (pickup -> dropoff)</div>
      <div class="legend-item"><span class="legend-swatch" style="background:#6c757d"></span>Idle</div>
    </div>
    <div class="totals">
      <div id="deadheadTotal">Total deadhead: 0.0 mi</div>
      <div id="tripTotal">Total trip miles: 0.0 mi</div>
    </div>
    <div class="status-list" id="vehicleStatus"></div>
  </div>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    const trajectories = {json.dumps(trajectories)};
    const map = L.map('map').setView([{center_lat}, {center_lon}], {zoom});
    L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap contributors'
    }}).addTo(map);

    const layers = [];
    const markers = new Map(); // vehicle_id -> marker
    const statuses = new Map(); // vehicle_id -> status string
    let idx = 0;
    let playing = false;
    let skipRequested = false;
    let rafId = null;
    const statusEl = document.getElementById('status');
    const statusListEl = document.getElementById('vehicleStatus');
    const speedFactor = 120; // ms per simulated minute (lower = faster)
    const deadheadTotalEl = document.getElementById('deadheadTotal');
    const tripTotalEl = document.getElementById('tripTotal');

    function setStatusText(text) {{
      statusEl.textContent = text;
    }}

    function updateStatus(vehicleId, state, requestId) {{
      statuses.set(vehicleId, state);
      renderStatusList();
      setStatusText("Vehicle " + vehicleId + ": " + state + " (req " + requestId + ")");
    }}

    function updateTotals() {{
      const deadhead = trajectories.reduce((sum, t) => sum + (t.deadhead_miles || 0), 0);
      const trips = trajectories.reduce((sum, t) => sum + (t.trip_miles || 0), 0);
      deadheadTotalEl.textContent = "Total deadhead: " + deadhead.toFixed(2) + " mi";
      tripTotalEl.textContent = "Total trip miles: " + trips.toFixed(2) + " mi";
    }}

    function renderStatusList() {{
      const entries = Array.from(statuses.entries());
      statusListEl.innerHTML = entries.map(([vid, state]) => {{
        const color = state === 'idle' ? '#6c757d' : state === 'to_pickup' ? '#ff3b30' : '#34c759';
        return '<div class="status-entry"><span class="legend-swatch" style="background:' + color + '"></span>' + vid + ' — ' + state + '</div>';
      }}).join('');
    }}

    function ensureMarker(vehicleId, start) {{
      if (!markers.has(vehicleId) && start) {{
        const marker = L.circleMarker([start.latitude, start.longitude], {{
          radius: 6,
          color: '#1e90ff',
          weight: 2,
          fillOpacity: 0.7
        }}).addTo(map).bindPopup("Vehicle " + vehicleId);
        markers.set(vehicleId, marker);
        statuses.set(vehicleId, 'idle');
        renderStatusList();
      }}
    }}

    function animateSegment(vehicleId, fromLoc, toLoc, minutes, color, done) {{
      if (!fromLoc || !toLoc) {{
        done();
        return;
      }}
      const durationMs = Math.max(300, minutes * speedFactor);
      const startLat = fromLoc.latitude;
      const startLon = fromLoc.longitude;
      const deltaLat = toLoc.latitude - startLat;
      const deltaLon = toLoc.longitude - startLon;

      const poly = L.polyline([[startLat, startLon], [toLoc.latitude, toLoc.longitude]], {{
        color: color,
        weight: 3,
        opacity: 0.75
      }}).addTo(map);
      layers.push(poly);

      const marker = markers.get(vehicleId);
      const startTime = performance.now();

      function step(now) {{
        if (skipRequested) {{
          skipRequested = false;
          marker.setLatLng([toLoc.latitude, toLoc.longitude]);
          done();
          return;
        }}
        const progress = Math.min(1, (now - startTime) / durationMs);
        const lat = startLat + deltaLat * progress;
        const lon = startLon + deltaLon * progress;
        marker.setLatLng([lat, lon]);
        if (progress < 1) {{
          rafId = requestAnimationFrame(step);
        }} else {{
          done();
        }}
      }}

      rafId = requestAnimationFrame(step);
    }}

    function playTrajectory(traj, finished) {{
      const vehicleId = traj.vehicle_id;
      const reqId = traj.request_id;
      if (!vehicleId || !traj.vehicle_start || !traj.pickup || !traj.dropoff) {{
        finished();
        return;
      }}

      ensureMarker(vehicleId, traj.vehicle_start);
      updateStatus(vehicleId, 'to_pickup', reqId);

      animateSegment(vehicleId, traj.vehicle_start, traj.pickup, traj.deadhead_minutes || 5, '#ff3b30', () => {{
        updateStatus(vehicleId, 'occupied', reqId);
        animateSegment(vehicleId, traj.pickup, traj.dropoff, traj.trip_minutes || 8, '#34c759', () => {{
          updateStatus(vehicleId, 'idle', reqId);
          finished();
        }});
      }});
    }}

    function play() {{
      if (idx >= trajectories.length) {{
        setStatusText('Done');
        playing = false;
        return;
      }}
      playing = true;
      setStatusText('Animating ' + (idx + 1) + ' / ' + trajectories.length);
      playTrajectory(trajectories[idx], () => {{
        idx += 1;
        if (playing) {{
          setTimeout(play, 150);
        }}
      }});
    }}

    function reset() {{
      if (rafId) {{
        cancelAnimationFrame(rafId);
        rafId = null;
      }}
      layers.forEach(l => map.removeLayer(l));
      layers.length = 0;
      markers.forEach(m => map.removeLayer(m));
      markers.clear();
      statuses.clear();
      idx = 0;
      playing = false;
      skipRequested = false;
      setStatusText('Idle');
      renderStatusList();
    }}

    document.getElementById('playBtn').onclick = () => {{
      if (!playing) {{
        play();
      }}
    }};

    document.getElementById('nextBtn').onclick = () => {{
      if (!playing && idx < trajectories.length) {{
        // start playback and immediately skip the first segment
        skipRequested = true;
        play();
      }} else {{
        skipRequested = true;
      }}
    }};

    document.getElementById('resetBtn').onclick = reset;

    // Seed markers so vehicles appear immediately
    trajectories.forEach(t => {{
      if (t.vehicle_id && t.vehicle_start) {{
        ensureMarker(t.vehicle_id, t.vehicle_start);
      }}
    }});
    renderStatusList();
    updateTotals();
  </script>
</body>
</html>
"""

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_template)

        self.logger.info(f"Map visualization saved to {output_path}")

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
