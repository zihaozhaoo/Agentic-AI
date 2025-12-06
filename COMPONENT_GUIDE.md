# Green Agent Framework - Complete Component Guide

This document provides a detailed explanation of each component in the Green Agent evaluation framework, how they interact, and how to use them.

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Component Details](#component-details)
3. [Data Flow](#data-flow)
4. [Running the System](#running-the-system)
5. [Logging and Debugging](#logging-and-debugging)
6. [Performance Optimization](#performance-optimization)

---

## Architecture Overview

The Green Agent framework consists of 6 main modules:

```
┌──────────────────────────────────────────────────────────────────┐
│                     GREEN AGENT FRAMEWORK                         │
│                                                                    │
│  ┌──────────────┐    ┌───────────────┐    ┌──────────────────┐  │
│  │   Request    │───>│  White Agent  │───>│     Vehicle      │  │
│  │  Simulation  │    │  (Under Test) │    │    Simulator     │  │
│  └──────────────┘    └───────────────┘    └──────────────────┘  │
│         │                     │                      │            │
│         │                     │                      │            │
│         └─────────────────────┴──────────────────────┘            │
│                               │                                   │
│                      ┌────────▼────────┐                          │
│                      │    Evaluator    │                          │
│                      └─────────────────┘                          │
│                                                                    │
│                     ┌────────────────────┐                        │
│                     │   Event Logger     │ (Tracks everything)    │
│                     └────────────────────┘                        │
└──────────────────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. Request Simulation (`src/request_simulation/`)

**Purpose**: Generate realistic natural language ride requests from trip data.

#### Key Classes

**`RequestSimulator`**
- **Location**: `src/request_simulation/request_simulator.py`
- **Purpose**: Main orchestrator for request generation
- **Methods**:
  - `load_and_preprocess_data()`: Load trip data from Parquet files
  - `simulate_requests()`: Generate NL requests from trip data
  - `augment_trip_with_context()`: Add POI, customer profiles, time constraints

**Example Usage**:
```python
from request_simulation import RequestSimulator

simulator = RequestSimulator(
    taxi_zone_lookup_path="taxi_zone_lookup.csv",
    template_ratio=0.5  # 50% templates, 50% LLM
)

# Load trip data
df = simulator.load_and_preprocess_data("trip_data.parquet", sample_size=1000)

# Generate requests
requests = simulator.simulate_requests(df, n_requests=100)
```

**Output Format**:
```python
{
    'trip_id': '12345',
    'request_time': datetime(2025, 1, 5, 14, 30),
    'pickup_zone': 'Midtown Center',
    'dropoff_zone': 'JFK Airport',
    'request': 'I need a ride from Times Square to JFK Airport at 3pm',
    'has_arrival_constraint': True,
    'requested_dropoff_time': datetime(2025, 1, 5, 17, 0),
    # ... more fields
}
```

---

### 2. White Agent Interface (`src/white_agent/`)

**Purpose**: Define the contract for agents under evaluation.

#### Key Classes

**`WhiteAgentBase`** (Abstract Base Class)
- **Location**: `src/white_agent/base_agent.py`
- **Purpose**: Interface that all white agents must implement
- **Required Methods**:

```python
class MyAgent(WhiteAgentBase):
    def parse_request(self, nl_request, vehicle_database):
        """
        Extract structured information from natural language.

        Args:
            nl_request: NaturalLanguageRequest object
            vehicle_database: Access to fleet state

        Returns:
            StructuredRequest with extracted info
        """
        # TODO: Implement parsing logic
        pass

    def make_routing_decision(self, structured_request, vehicle_database):
        """
        Select vehicle and estimate metrics.

        Args:
            structured_request: Parsed request
            vehicle_database: Access to fleet state

        Returns:
            RoutingDecision with vehicle assignment
        """
        # TODO: Implement routing logic
        pass

    def query_distance_and_time(self, origin, destination):
        """
        Calculate distance and time between locations.

        Returns:
            (distance_miles, duration_minutes)
        """
        # TODO: Use Google Maps API or routing engine
        pass
```

#### Data Structures

**`NaturalLanguageRequest`**
- Input from user (what the white agent receives)
- Contains: `request_id`, `request_time`, `natural_language_text`
- Optionally includes `ground_truth` for evaluation

**`StructuredRequest`**
- Parsed request (what the white agent extracts)
- Contains: origin, destination, time constraints, special requirements

**`RoutingDecision`**
- Vehicle assignment (what the white agent decides)
- Contains: vehicle_id, estimated times/distances

**Example**:
```python
# Input
nl_request = NaturalLanguageRequest(
    request_id="123",
    request_time=datetime.now(),
    natural_language_text="I need a wheelchair-accessible ride from Times Square to JFK at 3pm"
)

# Output 1: Parsed Request
structured_request = StructuredRequest(
    origin=Location(lat=40.758, lon=-73.985, zone_id=161),
    destination=Location(lat=40.641, lon=-73.778, zone_id=132),
    requested_pickup_time=datetime(..., 15, 0),
    wheelchair_accessible=True,
    ...
)

# Output 2: Routing Decision
routing_decision = RoutingDecision(
    vehicle_id="V000042",
    estimated_pickup_time=datetime(..., 15, 5),
    estimated_dropoff_time=datetime(..., 15, 50),
    estimated_pickup_distance_miles=2.3,
    ...
)
```

---

### 3. Vehicle System (`src/vehicle_system/`)

**Purpose**: Manage fleet and simulate vehicle movements.

#### Key Classes

**`Vehicle`**
- **Location**: `src/vehicle_system/vehicle.py`
- **Purpose**: Represent individual vehicle state
- **Attributes**:
  - `vehicle_id`: Unique identifier
  - `current_location`: Geographic location
  - `status`: IDLE, EN_ROUTE_TO_PICKUP, ON_TRIP, OFFLINE
  - `wheelchair_accessible`: Boolean
  - `trip_history`: List of completed trips
  - `total_miles_driven`: Cumulative mileage
  - `total_deadhead_miles`: Empty miles driven

**`VehicleDatabase`**
- **Location**: `src/vehicle_system/vehicle_database.py`
- **Purpose**: Fleet management with spatial queries
- **Key Methods**:
  - `get_available_vehicles()`: Query available vehicles
  - `get_vehicle_by_id()`: Get specific vehicle
  - `initialize_fleet()`: Initialize vehicles at realistic locations
  - `get_fleet_statistics()`: Get fleet metrics

**Example**:
```python
# Query available vehicles near a location
vehicles = vehicle_database.get_available_vehicles(
    location=origin,
    radius_miles=5.0,
    max_count=10,
    wheelchair_required=True
)

# Get specific vehicle
vehicle = vehicle_database.get_vehicle_by_id("V000042")

# Get fleet stats
stats = vehicle_database.get_fleet_statistics()
# Returns: total_vehicles, available_vehicles, total_miles_driven, etc.
```

**`VehicleSimulator`**
- **Location**: `src/vehicle_system/vehicle_simulator.py`
- **Purpose**: Simulate vehicle movements and trip execution
- **Key Methods**:
  - `execute_routing_decision()`: Execute white agent's decision
  - `simulate_trip_completion()`: Complete a trip
  - `advance_time()`: Move simulation forward in time

---

### 4. Evaluation System (`src/evaluation/`)

**Purpose**: Measure white agent performance.

#### Key Classes

**`Evaluator`**
- **Location**: `src/evaluation/evaluator.py`
- **Purpose**: Calculate performance metrics
- **Metrics Tracked**:

**Parsing Metrics**:
- Origin/destination zone accuracy
- Location error (miles)
- Time constraint accuracy
- Special requirements accuracy

**Routing Metrics**:
- Total revenue
- Total idle cost (deadhead miles × $0.50/mile)
- Net revenue (revenue - idle cost)
- Deadhead ratio (empty miles / total miles)
- Average pickup time
- Revenue per mile

**Example**:
```python
evaluator = Evaluator(
    idle_cost_per_mile=0.50,
    unmet_demand_penalty=50.0
)

# Evaluate single request
evaluator.evaluate_request(nl_request, parsed_request, routing_decision, trip_result)

# Get summary
summary = evaluator.get_summary()
print(f"Overall Score: {summary['overall_score']}/100")
print(f"Net Revenue: ${summary['routing_metrics']['net_revenue']}")
```

---

### 5. Environment (`src/environment/`)

**Purpose**: Orchestrate the complete evaluation pipeline.

#### Key Class

**`GreenAgentEnvironment`**
- **Location**: `src/environment/green_agent_environment.py`
- **Purpose**: Main coordinator for all components
- **Key Methods**:
  - `initialize_vehicles()`: Setup fleet with realistic locations
  - `generate_requests_from_data()`: Generate requests from trip data
  - `run_evaluation()`: Run complete evaluation
  - `save_results()`: Save results to JSON

**Complete Example**:
```python
from request_simulation import RequestSimulator
from environment import GreenAgentEnvironment
from white_agent import MyCustomAgent

# 1. Initialize request simulator
simulator = RequestSimulator(taxi_zone_lookup_path="zones.csv")

# 2. Create environment
env = GreenAgentEnvironment(request_simulator=simulator)

# 3. Initialize vehicles (use trip data for realistic locations!)
env.initialize_vehicles(
    num_vehicles=1000,
    sample_parquet_path="trip_data.parquet",
    sample_size=5000  # Sample 5K trips for location distribution
)

# 4. Generate requests
requests = env.generate_requests_from_data(
    parquet_path="trip_data.parquet",
    n_requests=1000
)

# 5. Create white agent
agent = MyCustomAgent()

# 6. Run evaluation
results = env.run_evaluation(
    white_agent=agent,
    requests=requests,
    verbose=True
)

# 7. Save results
env.save_results(results, "results/evaluation.json")
```

---

### 6. Logging System (`src/utils/`)

**Purpose**: Comprehensive event tracking for debugging.

#### Key Class

**`EventLogger`**
- **Location**: `src/utils/event_logger.py`
- **Purpose**: Track all events during evaluation
- **Events Logged**:
  - Vehicle initialization
  - Request arrivals
  - Parsing results
  - Routing decisions
  - Vehicle assignments
  - Vehicle movements
  - Trip completions
  - Errors

**Example**:
```python
from utils import EventLogger

# Create logger
logger = EventLogger(
    log_file_path="logs/evaluation.log",
    console_level=logging.WARNING,  # Only show warnings in console
    file_level=logging.DEBUG,  # Log everything to file
    enable_json_log=True  # Create JSON event log
)

# Pass to environment
env = GreenAgentEnvironment(request_simulator=simulator, logger=logger)

# After evaluation, save JSON log
logger.save_json_log("logs/events.json")

# Query events
trip_events = logger.get_events_for_request("12345")
vehicle_events = logger.get_events_for_vehicle("V000042")
```

**Event Log Format**:
```json
{
  "timestamp": "2025-01-05T14:30:00",
  "event_type": "VEHICLE_ASSIGNMENT",
  "event_data": {
    "vehicle_id": "V000042",
    "request_id": "12345",
    "current_location": {"latitude": 40.758, "longitude": -73.985},
    "pickup_location": {"latitude": 40.762, "longitude": -73.982},
    "estimated_pickup_distance_miles": 0.4,
    "estimated_pickup_time_minutes": 3.2
  }
}
```

---

## Data Flow

### Complete Request Processing Flow

```
1. Request Generation
   ├─> Load trip data from Parquet
   ├─> Sample trips and generate NL requests
   └─> Output: List of NaturalLanguageRequest objects

2. Request Arrival (logged by EventLogger)
   └─> Log: REQUEST_ARRIVAL

3. Parsing
   ├─> White Agent.parse_request()
   ├─> Extract: origin, destination, constraints
   ├─> Log: REQUEST_PARSED
   └─> Output: StructuredRequest

4. Routing Decision
   ├─> White Agent.make_routing_decision()
   ├─> Query vehicle_database for available vehicles
   ├─> Select vehicle and estimate metrics
   ├─> Log: ROUTING_DECISION, VEHICLE_ASSIGNMENT
   └─> Output: RoutingDecision

5. Trip Execution
   ├─> VehicleSimulator.execute_routing_decision()
   ├─> Update vehicle status
   ├─> Simulate trip
   ├─> Log: VEHICLE_MOVEMENT, TRIP_COMPLETE
   └─> Output: Trip result

6. Evaluation
   ├─> Evaluator.evaluate_request()
   ├─> Compare parsed vs ground truth
   ├─> Calculate routing metrics
   └─> Update cumulative statistics

7. Final Results
   ├─> Evaluator.get_summary()
   ├─> Log: EVALUATION_END
   └─> Save results and event log
```

---

## Running the System

### Option 1: Using the Demo Script

```bash
python examples/demo_evaluation.py
```

**What it does**:
1. Initializes request simulator
2. Creates event logger
3. Initializes environment
4. Initializes 100 vehicles from trip data
5. Generates 10 ride requests
6. Evaluates dummy agent
7. Saves results and logs

### Option 2: Custom Evaluation

```python
# See examples/custom_white_agent_example.py
from white_agent import WhiteAgentBase

class MyAgent(WhiteAgentBase):
    # Implement parse_request(), make_routing_decision(), query_distance_and_time()
    ...

# Run evaluation
env.run_evaluation(white_agent=MyAgent(), requests=requests)
```

### Option 3: Batch Evaluation

```python
agents = [Agent1(), Agent2(), Agent3()]
results_list = []

for agent in agents:
    results = env.run_evaluation(agent, requests)
    results_list.append(results)

# Compare agents
for r in results_list:
    print(f"{r['agent_name']}: {r['evaluation_summary']['overall_score']}/100")
```

---

## Logging and Debugging

### Debugging High Deadhead Miles

If you see unrealistic deadhead miles (like 5000 miles for 10 trips):

**Cause**: Vehicles initialized at incorrect locations or ground truth requests missing coordinates

**Solution**:
1. **Always initialize vehicles from trip data**:
   ```python
   env.initialize_vehicles(
       num_vehicles=100,
       sample_parquet_path="trip_data.parquet",  # REQUIRED!
       sample_size=1000
   )
   ```

2. **Check request coordinates**:
   ```python
   # In event log, check REQUEST_ARRIVAL events
   # origin/destination should have valid lat/lon (not 0.0, 0.0)
   ```

3. **Verify vehicle locations**:
   ```python
   stats = vehicle_database.get_fleet_statistics()
   for vehicle in vehicle_database.get_all_vehicles()[:5]:
       print(f"{vehicle.vehicle_id}: {vehicle.current_location.latitude}, {vehicle.current_location.longitude}")
   ```

### Using Event Logs for Debugging

```python
import json

# Load event log
with open("logs/events.json") as f:
    events = json.load(f)

# Find all events for a specific request
request_events = [e for e in events if e['event_data'].get('request_id') == '12345']

for event in request_events:
    print(f"{event['event_type']}: {event['event_data']}")

# Trace vehicle movements
vehicle_events = [e for e in events if e['event_data'].get('vehicle_id') == 'V000042']
```

### Log Files Created

After running evaluation:
- **`logs/evaluation.log`**: Text log with all events
- **`logs/events.json`**: JSON event log for programmatic analysis
- **`results/demo_evaluation.json`**: Evaluation results

---

## Performance Optimization

### 1. Vehicle Initialization

**Problem**: Vehicles initialized far from actual trip locations
**Solution**: Sample from trip data

```python
# BAD: Random locations
env.initialize_vehicles(num_vehicles=100)

# GOOD: Sample from trip data
env.initialize_vehicles(
    num_vehicles=100,
    sample_parquet_path="trip_data.parquet",
    sample_size=5000  # Sample 5K trips for good coverage
)
```

### 2. Request Generation

**Problem**: Slow LLM-based generation
**Solution**: Use templates for development

```python
# Fast (templates only)
simulator = RequestSimulator(template_ratio=1.0)

# Slow but realistic (50% LLM)
simulator = RequestSimulator(template_ratio=0.5)
```

### 3. Routing Optimization

**Problem**: Selecting first available vehicle (naive)
**Solution**: Optimize vehicle selection

```python
def make_routing_decision(self, structured_request, vehicle_database):
    # Get vehicles sorted by distance
    vehicles = vehicle_database.get_available_vehicles(
        location=structured_request.origin,
        radius_miles=10.0,
        max_count=10
    )

    # Select nearest (already sorted by distance)
    selected_vehicle = vehicles[0]
    ...
```

### 4. Distance Calculation

**Problem**: Repeated API calls
**Solution**: Cache results

```python
from functools import lru_cache

@lru_cache(maxsize=10000)
def query_distance_and_time(self, origin_tuple, dest_tuple):
    # Use Google Maps API
    ...
```

---

## Troubleshooting

### Common Issues

**1. `ModuleNotFoundError: No module named 'request_simulation'`**
- **Cause**: `src/` not in Python path
- **Solution**: Run from project root or use demo script which adds `src/` to path

**2. Negative net revenue**
- **Cause**: High deadhead miles (vehicles far from pickups)
- **Solution**: Initialize vehicles from trip data (see above)

**3. Zero trip miles**
- **Cause**: Trip simulation not completing properly
- **Solution**: Check event log for TRIP_COMPLETE events, verify coordinates

**4. Low parsing accuracy**
- **Cause**: Dummy agent doesn't actually parse, just uses ground truth
- **Solution**: Implement real parsing in your custom agent

---

## Next Steps

1. **Implement Your Own Agent**: See `examples/custom_white_agent_example.py`
2. **Add NLP Parsing**: Use LLMs (GPT-4, Claude) or NER models
3. **Optimize Routing**: Implement better vehicle selection algorithms
4. **Scale Up**: Test with 1K-10K requests
5. **Compare Agents**: Evaluate multiple strategies

---

## File Structure

```
Agentic-AI/
├── src/
│   ├── request_simulation/    # Generate NL requests
│   │   └── request_simulator.py
│   ├── white_agent/            # Agent interface
│   │   ├── data_structures.py
│   │   └── base_agent.py
│   ├── vehicle_system/         # Fleet management
│   │   ├── vehicle.py
│   │   ├── vehicle_database.py
│   │   └── vehicle_simulator.py
│   ├── evaluation/             # Performance metrics
│   │   └── evaluator.py
│   ├── environment/            # Main orchestrator
│   │   └── green_agent_environment.py
│   └── utils/                  # Logging
│       └── event_logger.py
├── examples/
│   ├── demo_evaluation.py
│   └── custom_white_agent_example.py
├── logs/                       # Generated logs
├── results/                    # Generated results
└── COMPONENT_GUIDE.md         # This file
```

---

For more information, see:
- **Framework README**: `FRAMEWORK_README.md`
- **Original README**: `README.md`
- **Proposal**: `Proposal.md`
