# Green Agent Evaluation Framework

A comprehensive code framework for evaluating AI agents on urban ride-hailing dispatch tasks.

## Overview

This framework provides a complete evaluation environment with:
- **White Agent Interface**: Abstract class for implementing dispatch algorithms
- **Vehicle System**: Database and simulator for fleet management
- **Evaluation System**: Metrics for parsing accuracy and routing efficiency
- **Green Agent Environment**: Orchestrator that coordinates all components

## Quick Start

### Run the Demo

```bash
python examples/demo_evaluation.py
```

This will evaluate a dummy white agent on 10 sample requests.

### Implement Your Own Agent

See `examples/custom_white_agent_example.py` for a complete template:

```python
from white_agent import WhiteAgentBase

class MyAgent(WhiteAgentBase):
    def parse_request(self, nl_request, vehicle_database):
        # Extract structured info from natural language
        return StructuredRequest(...)

    def make_routing_decision(self, structured_request, vehicle_database):
        # Select vehicle and estimate metrics
        return RoutingDecision(...)

    def query_distance_and_time(self, origin, destination):
        # Calculate distance and time
        return distance_miles, duration_minutes
```

## Framework Components

### 1. White Agent Interface (`src/white_agent/`)

**Data Structures:**
- `NaturalLanguageRequest`: Input from users (natural language text)
- `StructuredRequest`: Parsed request (origin, destination, constraints)
- `RoutingDecision`: Vehicle assignment decision
- `Location`: Geographic location with coordinates and zone info

**Base Class:**
- `WhiteAgentBase`: Abstract class to inherit from
- `DummyWhiteAgent`: Example implementation for testing

### 2. Vehicle System (`src/vehicle_system/`)

**Classes:**
- `Vehicle`: Individual vehicle with status, location, trip history
- `VehicleDatabase`: Fleet management with spatial queries
- `VehicleSimulator`: Simulates vehicle movements and trip execution

**Features:**
```python
# Query available vehicles
vehicles = vehicle_database.get_available_vehicles(
    location=origin,
    radius_miles=5.0,
    max_count=10,
    wheelchair_required=True
)

# Get fleet statistics
stats = vehicle_database.get_fleet_statistics()
```

### 3. Evaluation System (`src/evaluation/`)

**Metrics:**

**Parsing Metrics:**
- Origin/destination zone accuracy
- Location error (miles)
- Time constraint accuracy
- Special requirements accuracy

**Routing Metrics:**
- Net Revenue = Total Revenue - Idle Cost
- Deadhead Ratio = Empty Miles / Total Miles
- Average Pickup Time
- Revenue per Mile

**Evaluator:**
```python
evaluator = Evaluator(
    idle_cost_per_mile=0.50,
    unmet_demand_penalty=50.0
)

# Evaluate single request
evaluator.evaluate_request(nl_request, parsed_request, routing_decision, trip_result)

# Get summary
summary = evaluator.get_summary()
```

### 4. Environment (`src/environment/`)

**Main Orchestrator:**
```python
from environment import GreenAgentEnvironment

# Initialize
env = GreenAgentEnvironment(request_simulator)

# Setup vehicles
env.initialize_vehicles(num_vehicles=1000)

# Generate requests
requests = env.generate_requests_from_data(
    parquet_path="data.parquet",
    n_requests=100
)

# Run evaluation
results = env.run_evaluation(
    white_agent=my_agent,
    requests=requests,
    verbose=True
)

# Save results
env.save_results(results, "results/evaluation.json")
```

## Project Structure

```
Agentic-AI/
├── src/
│   ├── request_simulation/         # Natural language generation (existing)
│   │   └── request_simulator.py
│   │
│   ├── white_agent/                # NEW: White agent interface
│   │   ├── data_structures.py      # Request/response formats
│   │   ├── base_agent.py          # Abstract base class
│   │   └── __init__.py
│   │
│   ├── vehicle_system/             # NEW: Vehicle management
│   │   ├── vehicle.py             # Vehicle class
│   │   ├── vehicle_database.py    # Fleet database
│   │   ├── vehicle_simulator.py   # Movement simulation
│   │   └── __init__.py
│   │
│   ├── evaluation/                 # NEW: Performance evaluation
│   │   ├── evaluator.py           # Metrics and scoring
│   │   └── __init__.py
│   │
│   └── environment/                # NEW: Main orchestrator
│       ├── green_agent_environment.py
│       └── __init__.py
│
├── examples/
│   ├── demo_evaluation.py          # Demo script
│   └── custom_white_agent_example.py
│
├── results/                        # Evaluation results (generated)
├── FRAMEWORK_README.md            # This file
└── README.md                       # Original README
```

## Data Flow

```
┌─────────────────┐
│ RequestSimulator│ Generates natural language requests
└────────┬────────┘
         │
         v
┌─────────────────┐
│ NaturalLanguage │ "I need a ride from Times Square to JFK..."
│    Request      │
└────────┬────────┘
         │
         v
┌─────────────────┐
│  White Agent    │ parse_request()
│ (Under Test)    │ ────> StructuredRequest (origin, dest, time)
│                 │
│                 │ make_routing_decision()
│                 │ ────> RoutingDecision (vehicle, estimates)
└────────┬────────┘
         │
         v
┌─────────────────┐
│ VehicleSimulator│ Executes decision, simulates trip
└────────┬────────┘
         │
         v
┌─────────────────┐
│   Evaluator     │ Scores parsing + routing performance
└─────────────────┘
```

## API Reference

### WhiteAgentBase

```python
class WhiteAgentBase(ABC):
    @abstractmethod
    def parse_request(
        self,
        nl_request: NaturalLanguageRequest,
        vehicle_database: VehicleDatabase
    ) -> StructuredRequest:
        """Parse natural language into structured format."""
        pass

    @abstractmethod
    def make_routing_decision(
        self,
        structured_request: StructuredRequest,
        vehicle_database: VehicleDatabase
    ) -> RoutingDecision:
        """Select vehicle and estimate metrics."""
        pass

    @abstractmethod
    def query_distance_and_time(
        self,
        origin: Location,
        destination: Location
    ) -> tuple[float, float]:
        """Calculate distance and time between locations."""
        pass
```

### VehicleDatabase

```python
class VehicleDatabase:
    def get_vehicle_by_id(self, vehicle_id: str) -> Optional[Vehicle]

    def get_all_vehicles(self) -> List[Vehicle]

    def get_available_vehicles(
        self,
        location: Optional[Location] = None,
        radius_miles: Optional[float] = None,
        max_count: Optional[int] = None,
        wheelchair_required: bool = False
    ) -> List[Vehicle]

    def get_fleet_statistics(self) -> Dict[str, Any]

    def initialize_fleet(
        self,
        num_vehicles: int,
        zone_distribution: Optional[Dict[int, float]] = None,
        wheelchair_accessible_ratio: float = 0.1
    )
```

### Evaluator

```python
class Evaluator:
    def evaluate_parsing(
        self,
        nl_request: NaturalLanguageRequest,
        parsed_request: StructuredRequest
    ) -> Dict[str, Any]

    def evaluate_routing(
        self,
        routing_decision: RoutingDecision,
        trip_result: Dict[str, Any]
    ) -> Dict[str, Any]

    def evaluate_request(
        self,
        nl_request: NaturalLanguageRequest,
        parsed_request: StructuredRequest,
        routing_decision: RoutingDecision,
        trip_result: Optional[Dict[str, Any]]
    )

    def get_summary(self) -> Dict[str, Any]
```

### GreenAgentEnvironment

```python
class GreenAgentEnvironment:
    def initialize_vehicles(
        self,
        num_vehicles: int,
        zone_distribution: Optional[Dict[int, float]] = None,
        wheelchair_accessible_ratio: float = 0.1
    )

    def generate_requests_from_data(
        self,
        parquet_path: str,
        n_requests: int = 100,
        augment_location: bool = False
    ) -> List[Dict[str, Any]]

    def run_evaluation(
        self,
        white_agent: WhiteAgentBase,
        requests: List[Dict[str, Any]],
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        verbose: bool = True
    ) -> Dict[str, Any]

    def save_results(self, results: Dict[str, Any], output_path: str)
```

## Example Usage

### Basic Evaluation

```python
from request_simulation import RequestSimulator
from white_agent import DummyWhiteAgent
from environment import GreenAgentEnvironment

# 1. Initialize request simulator
simulator = RequestSimulator(
    taxi_zone_lookup_path="taxi_zone_lookup.csv",
    template_ratio=1.0
)

# 2. Create environment
env = GreenAgentEnvironment(simulator)

# 3. Initialize vehicles
env.initialize_vehicles(num_vehicles=100)

# 4. Generate requests
requests = env.generate_requests_from_data(
    parquet_path="data.parquet",
    n_requests=10
)

# 5. Create white agent
agent = DummyWhiteAgent()

# 6. Run evaluation
results = env.run_evaluation(agent, requests)

# 7. Save results
env.save_results(results, "results/eval.json")
```

### Custom Agent with Google Maps

```python
from white_agent import WhiteAgentBase
import googlemaps

class GoogleMapsAgent(WhiteAgentBase):
    def __init__(self):
        super().__init__("GoogleMapsAgent")
        self.gmaps = googlemaps.Client(key="YOUR_API_KEY")

    def query_distance_and_time(self, origin, destination):
        result = self.gmaps.distance_matrix(
            origins=[(origin.latitude, origin.longitude)],
            destinations=[(destination.latitude, destination.longitude)]
        )

        distance_m = result['rows'][0]['elements'][0]['distance']['value']
        duration_s = result['rows'][0]['elements'][0]['duration']['value']

        return distance_m / 1609.34, duration_s / 60.0  # miles, minutes
```

## Configuration

### Fleet Size
- Development: 100 vehicles
- Validation: 1,000 vehicles
- Production: 10,000+ vehicles

### Request Dataset
- Development: 100 requests
- Validation: 1,000 requests
- Production: 100,000+ requests

### Evaluation Costs
```python
Evaluator(
    idle_cost_per_mile=0.50,      # Deadhead mile cost
    unmet_demand_penalty=50.0      # Failed assignment penalty
)
```

### Trip Pricing
```python
VehicleSimulator(
    base_fare=2.50,               # Base fare
    per_mile_rate=1.75,           # Per mile rate
    per_minute_rate=0.35          # Per minute rate
)
```

## Integration with Existing Code

This framework is designed to work with the existing `request_simulation` module:

```python
# The existing RequestSimulator generates natural language requests
from request_simulation import RequestSimulator

simulator = RequestSimulator(...)
requests = simulator.simulate_requests(df, n_requests=100)

# The new framework evaluates white agents on these requests
from environment import GreenAgentEnvironment

env = GreenAgentEnvironment(request_simulator=simulator)
results = env.run_evaluation(white_agent, requests)
```

## Next Steps

1. **Implement Your Agent**: Create a class inheriting from `WhiteAgentBase`
2. **Add NLP/LLM**: Implement robust natural language parsing
3. **Add Routing Logic**: Implement sophisticated vehicle assignment
4. **Scale Up**: Test with larger datasets (1K+ requests)
5. **Optimize**: Minimize deadhead miles and maximize net revenue

## Output Format

### Evaluation Results

```json
{
  "agent_name": "MyAgent",
  "evaluation_summary": {
    "parsing_metrics": {
      "origin_zone_accuracy": 0.85,
      "destination_zone_accuracy": 0.82,
      "mean_origin_error_miles": 0.25,
      "mean_destination_error_miles": 0.30
    },
    "routing_metrics": {
      "total_revenue": 5000.00,
      "total_idle_cost": 250.00,
      "net_revenue": 4750.00,
      "deadhead_ratio": 0.15,
      "average_pickup_time_minutes": 5.2
    },
    "overall_score": 78.5
  },
  "processed_requests": 100,
  "successful_requests": 98,
  "failed_requests": 2
}
```

## Tips for Implementation

1. **Parsing**: Use LLMs (GPT-4, Claude) or NER models for robust parsing
2. **Routing**: Consider both immediate response time and future demand
3. **Distance Calculation**: Use Google Maps API for accurate estimates
4. **Caching**: Cache distance queries to minimize API costs
5. **Testing**: Start with small datasets (10-100 requests) before scaling up

## Common Issues

**Problem**: "No vehicles available in database"
- **Solution**: Call `env.initialize_vehicles()` before running evaluation

**Problem**: High deadhead ratio
- **Solution**: Improve vehicle selection algorithm to choose closer vehicles

**Problem**: Low parsing accuracy
- **Solution**: Use more sophisticated NLP/LLM models for request parsing

## License

MIT License - See main README for details
