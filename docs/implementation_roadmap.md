# Implementation To-Do List

This document outlines the remaining implementation tasks for the Green Agent framework. The framework structure is complete, but the following components need real implementations.

---

## Current Status

### ✅ Completed Components
- [x] Request Simulation (Natural Language Generation)
- [x] White Agent Interface (Abstract classes and data structures)
- [x] Vehicle System (Database, simulation, realistic initialization)
- [x] Evaluation System (Parsing and routing metrics)
- [x] Environment Orchestrator (Complete pipeline)
- [x] Logging System (Comprehensive event tracking)
- [x] Documentation (Getting started, component guide)

### ❌ Components Requiring Implementation
The framework is **fully functional** with dummy implementations, but the following need **real implementations** for production use:

---

## Task 1: Natural Language Parsing Implementation

**Status**: Framework complete, dummy implementation provided
**Priority**: High
**Estimated Complexity**: Medium-High

### Current State
- `DummyWhiteAgent.parse_request()` simply returns ground truth (cheating)
- No actual NLP/LLM processing
- Works for testing but not for real evaluation

### What Needs to be Implemented

#### 1.1 NLP-Based Parser
**File**: `src/white_agent/parsers/nlp_parser.py` (to be created)

**Requirements**:
- [ ] Extract origin location from natural language
  - Parse POI names (e.g., "Times Square", "JFK Airport")
  - Parse addresses (e.g., "123 Main St, Manhattan")
  - Parse zone names (e.g., "Midtown", "Brooklyn")
  - Resolve to coordinates and zone IDs

- [ ] Extract destination location from natural language
  - Same requirements as origin

- [ ] Extract temporal constraints
  - Parse absolute times (e.g., "at 3pm", "14:30")
  - Parse relative times (e.g., "in 30 minutes", "ASAP")
  - Identify arrival vs departure constraints (e.g., "arrive by 5pm" vs "pick me up at 3pm")
  - Parse time windows (e.g., "between 2-3pm", "±10 minutes")

- [ ] Extract special requirements
  - Wheelchair accessibility (e.g., "wheelchair accessible", "disabled access")
  - Passenger count (e.g., "for 3 people", "group of 5")
  - Luggage (e.g., "3 large bags", "lots of luggage")
  - Shared ride preferences (e.g., "shared ride OK", "private car only")
  - Pet requirements
  - Child seat requirements

- [ ] Handle ambiguity and incomplete information
  - Provide confidence scores for extracted entities
  - Use defaults for missing information
  - Request clarification when critically ambiguous

**Implementation Options**:

**Option A: Named Entity Recognition (NER)**
```python
# Using spaCy or similar
import spacy

nlp = spacy.load("en_core_web_sm")
doc = nlp(natural_language_text)

# Extract locations
locations = [ent for ent in doc.ents if ent.label_ in ['GPE', 'LOC', 'FAC']]

# Extract times
times = [ent for ent in doc.ents if ent.label_ == 'TIME']
```

**Option B: LLM-Based Extraction (Recommended)**
```python
# Using GPT-4 or Claude
import openai

response = openai.ChatCompletion.create(
    model="gpt-4",
    messages=[{
        "role": "system",
        "content": "Extract structured ride request information from natural language."
    }, {
        "role": "user",
        "content": f"Extract origin, destination, time, and requirements from: {nl_text}"
    }],
    functions=[{
        "name": "extract_ride_info",
        "parameters": {
            "type": "object",
            "properties": {
                "origin": {"type": "string"},
                "destination": {"type": "string"},
                # ... more fields
            }
        }
    }]
)
```

**Option C: Hybrid Approach**
- Use regex/patterns for common templates
- Use NER for location extraction
- Use LLM for complex or ambiguous requests

#### 1.2 Geocoding Service Integration
**File**: `src/white_agent/geocoding/geocoder.py` (to be created)

**Requirements**:
- [ ] Convert POI names to coordinates
  - Use Google Places API, Nominatim, or similar
  - Handle multiple matches (e.g., "Penn Station" could be NYC or other cities)
  - Use context (e.g., NYC-only for this domain)

- [ ] Convert addresses to coordinates
  - Use geocoding API (Google, Mapbox, etc.)
  - Validate coordinates are within service area

- [ ] Map coordinates to taxi zones
  - Use shapefile or zone boundaries
  - Handle edge cases (locations on zone borders)

- [ ] Cache geocoding results
  - Avoid repeated API calls for same locations
  - Persistent cache across evaluations

**Example Implementation Skeleton**:
```python
class Geocoder:
    def __init__(self, api_key: str, cache_file: str):
        self.api_key = api_key
        self.cache = self._load_cache(cache_file)

    def geocode_poi(self, poi_name: str, context: str = "NYC") -> Location:
        # TODO: Query Google Places API
        # TODO: Filter by context (NYC only)
        # TODO: Return best match
        pass

    def geocode_address(self, address: str) -> Location:
        # TODO: Query geocoding API
        # TODO: Validate coordinates
        pass

    def coordinates_to_zone(self, lat: float, lon: float) -> int:
        # TODO: Use shapefile or zone boundaries
        # TODO: Find which zone contains the point
        pass
```

#### 1.3 Time Parser
**File**: `src/white_agent/parsers/time_parser.py` (to be created)

**Requirements**:
- [ ] Parse absolute times
  - "3pm", "15:00", "3:30 PM"
  - Handle timezone (assume NYC/Eastern)

- [ ] Parse relative times
  - "in 30 minutes", "in an hour"
  - "ASAP", "now", "immediately"

- [ ] Parse date+time
  - "tomorrow at 3pm"
  - "January 5 at 2:30pm"

- [ ] Distinguish pickup vs arrival constraints
  - "pick me up at 3pm" → pickup time
  - "arrive by 5pm" → arrival constraint
  - "I need to be there by 6pm" → arrival constraint

**Example Implementation**:
```python
from dateutil import parser
import re

class TimeParser:
    def parse_time(self, text: str, reference_time: datetime) -> dict:
        # TODO: Extract time expressions
        # TODO: Determine if pickup or arrival constraint
        # TODO: Parse time windows

        return {
            'requested_pickup_time': ...,
            'requested_dropoff_time': ...,
            'has_arrival_constraint': ...,
            'time_window_minutes': ...
        }
```

---

## Task 2: Intelligent Routing Algorithm Implementation

**Status**: Framework complete, naive implementation provided
**Priority**: High
**Estimated Complexity**: High

### Current State
- `DummyWhiteAgent.make_routing_decision()` just picks first available vehicle
- No optimization for distance, time, or system-level efficiency
- Works for testing but produces poor results (100% deadhead ratio)

### What Needs to be Implemented

#### 2.1 Nearest Vehicle Strategy (Baseline)
**File**: `src/white_agent/routing/nearest_vehicle.py` (to be created)

**Requirements**:
- [ ] Query available vehicles near pickup location
- [ ] Filter by special requirements (wheelchair, capacity, etc.)
- [ ] Select nearest vehicle by distance
- [ ] Calculate accurate pickup and trip times
- [ ] Handle no-vehicle-available cases

**Algorithm**:
```python
def nearest_vehicle_routing(request, vehicle_database):
    # 1. Get vehicles near origin
    vehicles = vehicle_database.get_available_vehicles(
        location=request.origin,
        radius_miles=10.0,
        max_count=50,
        wheelchair_required=request.wheelchair_accessible
    )

    # 2. Calculate distances for all vehicles
    vehicles_with_distance = []
    for vehicle in vehicles:
        distance, time = calculate_distance(vehicle.location, request.origin)
        vehicles_with_distance.append((vehicle, distance, time))

    # 3. Sort by distance
    vehicles_with_distance.sort(key=lambda x: x[1])

    # 4. Select best vehicle
    selected = vehicles_with_distance[0]

    # 5. Create routing decision
    return RoutingDecision(...)
```

#### 2.2 Predictive Routing Strategy
**File**: `src/white_agent/routing/predictive_routing.py` (to be created)

**Requirements**:
- [ ] Consider future demand patterns
  - Don't send vehicle to low-demand area after dropoff
  - Prefer vehicles that will end up in high-demand zones

- [ ] Consider vehicle positioning after trip
  - Calculate where vehicle will be after completing this trip
  - Estimate likelihood of getting next request quickly

- [ ] Time-based optimization
  - Don't assign vehicle if arrival time exceeds constraint
  - Prefer vehicles that can arrive within tighter windows

- [ ] Load balancing
  - Avoid overloading vehicles in high-demand areas
  - Spread vehicles across zones for better coverage

**Algorithm Skeleton**:
```python
def predictive_routing(request, vehicle_database, demand_predictor):
    # 1. Get candidate vehicles
    candidates = vehicle_database.get_available_vehicles(...)

    # 2. Score each vehicle
    scored_vehicles = []
    for vehicle in candidates:
        score = calculate_vehicle_score(
            vehicle=vehicle,
            request=request,
            future_demand=demand_predictor.predict(
                zone=get_dropoff_zone(request),
                time=request.time + trip_duration
            )
        )
        scored_vehicles.append((vehicle, score))

    # 3. Select best score
    best_vehicle = max(scored_vehicles, key=lambda x: x[1])

    return RoutingDecision(...)
```

#### 2.3 Global Optimization Strategy (Advanced)
**File**: `src/white_agent/routing/global_optimizer.py` (to be created)

**Requirements**:
- [ ] Batch multiple requests together
  - Collect requests over time window (e.g., 5 minutes)
  - Solve vehicle assignment problem jointly

- [ ] Use optimization solver (OR-Tools, PuLP, etc.)
  - Minimize total deadhead miles
  - Maximize satisfied requests
  - Respect time windows and constraints

- [ ] Handle dynamic arrivals
  - Re-optimize periodically as new requests arrive
  - Cancel/reassign vehicles if better solution found

**Algorithm Skeleton**:
```python
from ortools.linear_solver import pywraplp

def global_optimization(pending_requests, vehicle_database):
    # 1. Formulate as assignment problem
    solver = pywraplp.Solver.CreateSolver('SCIP')

    # 2. Decision variables: x[i,j] = 1 if vehicle j assigned to request i
    x = {}
    for i, request in enumerate(pending_requests):
        for j, vehicle in enumerate(vehicles):
            x[i,j] = solver.BoolVar(f'x_{i}_{j}')

    # 3. Objective: minimize total deadhead miles
    objective = solver.Objective()
    for i, request in enumerate(pending_requests):
        for j, vehicle in enumerate(vehicles):
            deadhead_distance = calculate_distance(vehicle.location, request.origin)
            objective.SetCoefficient(x[i,j], deadhead_distance)
    objective.SetMinimization()

    # 4. Constraints
    # Each request assigned to at most one vehicle
    for i in range(len(pending_requests)):
        solver.Add(sum(x[i,j] for j in range(len(vehicles))) <= 1)

    # Each vehicle assigned to at most one request
    for j in range(len(vehicles)):
        solver.Add(sum(x[i,j] for i in range(len(pending_requests))) <= 1)

    # 5. Solve
    status = solver.Solve()

    # 6. Extract assignments
    assignments = []
    for i in range(len(pending_requests)):
        for j in range(len(vehicles)):
            if x[i,j].solution_value() > 0.5:
                assignments.append((pending_requests[i], vehicles[j]))

    return assignments
```

#### 2.4 Ride-Sharing Support (Optional)
**File**: `src/white_agent/routing/rideshare.py` (to be created)

**Requirements**:
- [ ] Detect compatible requests (similar routes, overlapping times)
- [ ] Calculate shared route (pickup order, detour distance)
- [ ] Optimize for total distance savings
- [ ] Respect time constraints for all passengers
- [ ] Handle capacity limits

---

## Task 3: Real-Time Distance and Route Calculation

**Status**: Framework complete, Haversine approximation provided
**Priority**: Medium (can use approximations for development)
**Estimated Complexity**: Medium

### Current State
- `DummyWhiteAgent.query_distance_and_time()` uses Haversine distance (straight-line)
- No consideration for actual road network
- Assumes constant speed (25 mph)
- Works for rough estimates but not production-accurate

### What Needs to be Implemented

#### 3.1 Google Maps Distance Matrix Integration
**File**: `src/white_agent/routing/google_maps_client.py` (to be created)

**Requirements**:
- [ ] Query Google Maps Distance Matrix API
  - Calculate driving distance and time
  - Handle traffic conditions
  - Support multiple origin-destination pairs (batch queries)

- [ ] API rate limiting and quota management
  - Respect API quotas (e.g., 2500 free queries/day)
  - Implement retry logic with exponential backoff
  - Queue requests to avoid overwhelming API

- [ ] Caching strategy
  - Cache results for frequently queried routes
  - Use persistent cache across evaluations
  - Implement cache invalidation (time-based, e.g., daily)

- [ ] Fallback to approximations
  - Use Haversine when API unavailable
  - Use cached results when possible

**Implementation Skeleton**:
```python
import googlemaps
from functools import lru_cache
import time

class GoogleMapsClient:
    def __init__(self, api_key: str, cache_file: str = None):
        self.gmaps = googlemaps.Client(key=api_key)
        self.cache = self._load_cache(cache_file) if cache_file else {}
        self.request_count = 0
        self.request_limit = 2500  # Daily limit

    def query_distance_matrix(
        self,
        origins: List[Location],
        destinations: List[Location],
        mode: str = "driving",
        departure_time: datetime = None
    ) -> List[List[Dict]]:
        """
        Query distance and time for multiple origin-destination pairs.

        Returns:
            Matrix of results: [[{distance_miles, duration_minutes}, ...], ...]
        """
        # TODO: Check cache first
        # TODO: Check rate limit
        # TODO: Call API
        # TODO: Parse results
        # TODO: Cache results
        # TODO: Return formatted data
        pass

    def query_single(
        self,
        origin: Location,
        destination: Location
    ) -> tuple[float, float]:
        """
        Query distance and time for single pair.

        Returns:
            (distance_miles, duration_minutes)
        """
        # TODO: Check cache
        cache_key = f"{origin.latitude},{origin.longitude}_{destination.latitude},{destination.longitude}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        # TODO: Call API
        result = self.gmaps.distance_matrix(
            origins=[(origin.latitude, origin.longitude)],
            destinations=[(destination.latitude, destination.longitude)],
            mode="driving",
            units="imperial"
        )

        # TODO: Extract and return
        element = result['rows'][0]['elements'][0]
        distance_miles = element['distance']['value'] / 1609.34  # meters to miles
        duration_minutes = element['duration']['value'] / 60.0  # seconds to minutes

        # TODO: Cache result
        self.cache[cache_key] = (distance_miles, duration_minutes)

        return distance_miles, duration_minutes
```

#### 3.2 OSRM (Open Source Routing Machine) Integration
**File**: `src/white_agent/routing/osrm_client.py` (to be created)

**Requirements**:
- [ ] Set up local OSRM server or use public API
- [ ] Query routes between locations
- [ ] Extract distance and duration
- [ ] Parse turn-by-turn directions (optional)
- [ ] No API key required (free alternative to Google Maps)

**Advantages**:
- Free and unlimited
- Can run locally for speed
- Open source

**Disadvantages**:
- Requires setup (Docker container)
- May have less accurate traffic data than Google

**Implementation Skeleton**:
```python
import requests

class OSRMClient:
    def __init__(self, server_url: str = "http://router.project-osrm.org"):
        self.server_url = server_url

    def query_route(
        self,
        origin: Location,
        destination: Location
    ) -> tuple[float, float]:
        """
        Query route using OSRM.

        Returns:
            (distance_miles, duration_minutes)
        """
        # TODO: Format coordinates
        coords = f"{origin.longitude},{origin.latitude};{destination.longitude},{destination.latitude}"

        # TODO: Call OSRM API
        url = f"{self.server_url}/route/v1/driving/{coords}"
        params = {"overview": "false"}
        response = requests.get(url, params=params)

        # TODO: Parse response
        data = response.json()
        route = data['routes'][0]
        distance_meters = route['distance']
        duration_seconds = route['duration']

        # TODO: Convert units
        distance_miles = distance_meters / 1609.34
        duration_minutes = duration_seconds / 60.0

        return distance_miles, duration_minutes
```

#### 3.3 Hybrid Strategy with Intelligent Fallbacks
**File**: `src/white_agent/routing/distance_calculator.py` (to be created)

**Requirements**:
- [ ] Primary: Use Google Maps for accurate results
- [ ] Secondary: Use OSRM if Google Maps unavailable
- [ ] Tertiary: Use cached historical data
- [ ] Fallback: Use Haversine approximation with speed model

**Implementation Skeleton**:
```python
class DistanceCalculator:
    def __init__(
        self,
        google_maps_client: Optional[GoogleMapsClient] = None,
        osrm_client: Optional[OSRMClient] = None,
        cache_file: str = None
    ):
        self.google_maps = google_maps_client
        self.osrm = osrm_client
        self.cache = self._load_cache(cache_file) if cache_file else {}

    def calculate(
        self,
        origin: Location,
        destination: Location,
        use_cache: bool = True
    ) -> tuple[float, float]:
        """
        Calculate distance and time with intelligent fallbacks.
        """
        # TODO: Try cache first
        if use_cache:
            cached = self._check_cache(origin, destination)
            if cached:
                return cached

        # TODO: Try Google Maps
        if self.google_maps:
            try:
                result = self.google_maps.query_single(origin, destination)
                self._update_cache(origin, destination, result)
                return result
            except Exception as e:
                logger.warning(f"Google Maps failed: {e}, trying OSRM")

        # TODO: Try OSRM
        if self.osrm:
            try:
                result = self.osrm.query_route(origin, destination)
                self._update_cache(origin, destination, result)
                return result
            except Exception as e:
                logger.warning(f"OSRM failed: {e}, using Haversine")

        # TODO: Fallback to Haversine with speed model
        return self._haversine_with_speed_model(origin, destination)

    def _haversine_with_speed_model(
        self,
        origin: Location,
        destination: Location
    ) -> tuple[float, float]:
        """
        Haversine distance with speed model based on location type.
        """
        # TODO: Calculate straight-line distance
        distance = haversine_distance(origin, destination)

        # TODO: Apply routing factor (roads are not straight)
        distance *= 1.3  # Typical routing factor

        # TODO: Estimate speed based on area type
        if is_manhattan(origin) or is_manhattan(destination):
            speed_mph = 15.0  # Slow in Manhattan
        elif is_highway_route(origin, destination):
            speed_mph = 55.0  # Fast on highways
        else:
            speed_mph = 25.0  # Average city speed

        duration_minutes = (distance / speed_mph) * 60.0

        return distance, duration_minutes
```

---

## Summary

### Priority Order

1. **Task 2: Intelligent Routing** (Most Impact)
   - Even with dummy parsing (using ground truth), good routing dramatically improves results
   - Reduces deadhead miles from 100% to <30%
   - Relatively self-contained

2. **Task 1: NLP Parsing** (Core Functionality)
   - Required for real-world use (can't cheat with ground truth)
   - Enables evaluation of parsing accuracy
   - Can start with simple regex/templates, upgrade to LLM later

3. **Task 3: Distance Calculation** (Accuracy)
   - Haversine approximation works reasonably for development
   - Can be deferred until final evaluation
   - Most effort for incremental improvement

### Quick Wins for Each Task

**Task 1 Quick Win**: LLM-based extraction with structured outputs
- Use GPT-4 function calling to extract fields
- Implement in ~100 lines of code
- Achieves good accuracy quickly

**Task 2 Quick Win**: Nearest vehicle with proper distance calculation
- Replace first-available with nearest-available
- Reduces deadhead by 60-70% immediately
- Simple to implement

**Task 3 Quick Win**: Google Maps integration with caching
- Use googlemaps Python package
- Add simple LRU cache
- Works well for development/testing

### Testing Each Task

**Task 1 Test**:
```bash
# Compare parsing accuracy against ground truth
python test_parsing.py --agent MyAgent --requests 100
# Should achieve >80% zone accuracy, <0.5 mile location error
```

**Task 2 Test**:
```bash
# Compare routing efficiency
python test_routing.py --agent MyAgent --requests 1000
# Should achieve: Net Revenue > $500, Deadhead Ratio < 40%
```

**Task 3 Test**:
```bash
# Compare distance estimates vs ground truth
python test_distance.py --sample 100
# Should achieve: <10% error vs actual driving distance
```

---

## Notes

- All frameworks and interfaces are **already implemented**
- These tasks involve **filling in the implementation details**
- The system works end-to-end with dummy implementations
- Each task can be developed and tested independently
- Start with simple implementations, iterate to improve
