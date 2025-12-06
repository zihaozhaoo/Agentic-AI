# Getting Started with Green Agent Framework

## Quick Start (5 minutes)

```bash
# 1. Run the demo
python examples/demo_evaluation.py

# 2. Check the results
cat results/demo_evaluation.json

# 3. View the event log
python -c "import json; print(json.dumps(json.load(open('logs/events.json'))[:3], indent=2))"
```

## Understanding the Results

The demo evaluates a **DummyWhiteAgent** on 10 ride requests with a fleet of 100 vehicles.

### Expected Demo Results

```
Parsing Metrics: 100% accuracy
- The dummy agent "cheats" by using ground truth for parsing
- In your implementation, you'll need real NLP/LLM parsing

Routing Metrics: Baseline performance
- Net Revenue: ~$95 (positive!)
- Deadhead Ratio: ~17%
- Average Pickup Time: ~1.4 minutes
```

### How the Framework Handles Missing Coordinates

The demo uses `augment_location=False` to avoid Google Maps API calls, but the framework **automatically handles this**:

1. **Vehicles are initialized at realistic NYC locations** ✓
   - Sampled from actual trip data
   - Located in Manhattan, Brooklyn, Queens, etc.

2. **Requests automatically use zone centers when coordinates are missing** ✓
   - Trip data has zone IDs (e.g., zone 161 = "Midtown Center")
   - Framework maps zones to borough centers:
     - Manhattan: (40.76, -73.99)
     - Brooklyn: (40.68, -73.94)
     - Queens: (40.73, -73.79)
     - Bronx: (40.84, -73.86)
     - Staten Island: (40.58, -74.15)
   - Small random offset added to spread locations

3. **Result: Realistic distances** ✓
   - Pickup distances: 0.2-2 miles (typical for same borough)
   - Trip distances: 2-10 miles (typical NYC rides)
   - Deadhead ratio: 15-20% (industry baseline)

### How to Get Even Better Accuracy

**Option 1: Enable Location Augmentation** (Recommended for production)

```python
# In examples/demo_evaluation.py, change:
requests = environment.generate_requests_from_data(
    parquet_path=parquet_file,
    n_requests=10,
    augment_location=True  # Enable Google Maps API
)
```

This will:
- Query Google Maps for exact coordinates
- Use smart sampling to minimize API calls
- Cache results for efficiency

**Option 2: Use OSRM (Open Source Routing Machine)** (Free alternative)

Set up local OSRM server or use public API:
- Free and unlimited queries
- Good routing accuracy
- No API key required

**Option 3: Improve Routing Algorithm** (Biggest Impact)

The demo uses naive "first available vehicle" routing. Implement smarter strategies:

```python
class SmartAgent(WhiteAgentBase):
    def make_routing_decision(self, request, vehicle_database):
        # Get vehicles near origin (already sorted by distance)
        vehicles = vehicle_database.get_available_vehicles(
            location=request.origin,
            radius_miles=5.0,
            max_count=10
        )

        # Select nearest vehicle (instead of first available)
        selected_vehicle = vehicles[0]  # Already nearest due to sorting
        ...
```

Expected improvements:
- Deadhead ratio: 17% → 10-12%
- Average pickup time: 1.4 → 0.8 minutes
- Net revenue: $95 → $120+

## Running with Production-Quality Metrics

The demo already produces **realistic baseline metrics** using zone center approximations. To get **production-quality accuracy**:

### Step 1: Enable Location Augmentation (Optional)

For exact street-level coordinates:

```python
# In examples/demo_evaluation.py
requests = environment.generate_requests_from_data(
    parquet_path=parquet_file,
    n_requests=10,
    augment_location=True  # Use Google Maps API
)
```

### Step 2: Set API Key (if using augmentation)

```bash
export GOOGLE_MAPS_API_KEY="your-api-key-here"
```

### Step 3: Improve Routing Algorithm

The **biggest gains** come from better routing (not better coordinates):

```python
# Implement nearest-vehicle routing (see Task 2 in TODO.md)
# Expected improvement: 17% → 10% deadhead ratio
```

## Implementing Your Own Agent

### Step 1: Create Your Agent Class

```python
from white_agent import WhiteAgentBase
import googlemaps

class MySmartAgent(WhiteAgentBase):
    def __init__(self):
        super().__init__("MySmartAgent")
        self.gmaps = googlemaps.Client(key="YOUR_API_KEY")

    def parse_request(self, nl_request, vehicle_database):
        # TODO: Use NLP/LLM to extract information
        # For now, use ground truth (like dummy agent)
        return nl_request.ground_truth

    def make_routing_decision(self, structured_request, vehicle_database):
        # Get vehicles near origin, sorted by distance
        vehicles = vehicle_database.get_available_vehicles(
            location=structured_request.origin,
            radius_miles=5.0,
            max_count=10
        )

        if not vehicles:
            # Fallback: use any available vehicle
            vehicles = vehicle_database.get_available_vehicles(max_count=1)

        # Select nearest vehicle
        selected_vehicle = vehicles[0]

        # Calculate distances
        pickup_dist, pickup_time = self.query_distance_and_time(
            selected_vehicle.current_location,
            structured_request.origin
        )

        trip_dist, trip_time = self.query_distance_and_time(
            structured_request.origin,
            structured_request.destination
        )

        # Create decision
        from white_agent import RoutingDecision
        from datetime import timedelta

        return RoutingDecision(
            request_id=structured_request.request_id,
            vehicle_id=selected_vehicle.vehicle_id,
            estimated_pickup_time=structured_request.request_time + timedelta(minutes=pickup_time),
            estimated_dropoff_time=structured_request.request_time + timedelta(minutes=pickup_time+trip_time),
            estimated_pickup_distance_miles=pickup_dist,
            estimated_trip_distance_miles=trip_dist
        )

    def query_distance_and_time(self, origin, destination):
        # Use Google Maps Distance Matrix API
        result = self.gmaps.distance_matrix(
            origins=[(origin.latitude, origin.longitude)],
            destinations=[(destination.latitude, destination.longitude)],
            mode="driving"
        )

        # Extract distance and duration
        element = result['rows'][0]['elements'][0]
        distance_m = element['distance']['value']
        duration_s = element['duration']['value']

        return distance_m / 1609.34, duration_s / 60.0  # Convert to miles, minutes
```

### Step 2: Use Your Agent in Evaluation

```python
# In demo script, replace:
white_agent = DummyWhiteAgent()

# With:
white_agent = MySmartAgent()
```

### Step 3: Run and Compare

```bash
python examples/demo_evaluation.py
```

## Debugging with Event Logs

### View All Events

```bash
cat logs/events.json | jq '.[] | {type: .event_type, data: .event_data}'
```

### Find Events for Specific Request

```python
import json

with open('logs/events.json') as f:
    events = json.load(f)

request_id = "0"  # First request
request_events = [e for e in events if e.get('event_data', {}).get('request_id') == request_id]

for event in request_events:
    print(f"{event['event_type']}:")
    print(f"  {event['event_data']}")
    print()
```

### Check Vehicle Locations

```python
import json

with open('logs/events.json') as f:
    events = json.load(f)

# Get all vehicle assignments
assignments = [e for e in events if e['event_type'] == 'VEHICLE_ASSIGNMENT']

for a in assignments[:5]:  # First 5
    data = a['event_data']
    print(f"Vehicle {data['vehicle_id']}:")
    print(f"  Current: ({data['current_location']['latitude']:.4f}, {data['current_location']['longitude']:.4f})")
    print(f"  Pickup: ({data['pickup_location']['latitude']:.4f}, {data['pickup_location']['longitude']:.4f})")
    print(f"  Distance: {data['estimated_pickup_distance_miles']:.1f} miles")
    print()
```

## Scaling Up

### From Demo (10 requests) to Production (100K requests)

```python
# 1. Increase fleet size
environment.initialize_vehicles(
    num_vehicles=10000,  # Scale up from 100
    sample_parquet_path=parquet_file,
    sample_size=50000  # More trips for better location coverage
)

# 2. Generate more requests
requests = environment.generate_requests_from_data(
    parquet_path=parquet_file,
    n_requests=100000,  # Scale up from 10
    augment_location=True  # Use real coordinates
)

# 3. Run evaluation (will take longer)
results = environment.run_evaluation(
    white_agent=my_agent,
    requests=requests,
    verbose=True  # Show progress
)
```

## Performance Tips

### 1. Cache Distance Queries

```python
from functools import lru_cache

@lru_cache(maxsize=10000)
def query_distance_and_time(self, origin_tuple, dest_tuple):
    # Convert tuples back to Location objects
    origin = Location(*origin_tuple)
    destination = Location(*dest_tuple)

    # Query API
    ...
```

### 2. Batch API Calls

Instead of querying distance for each request individually, batch multiple queries:

```python
# Get distances for all vehicles at once
origins = [v.current_location for v in vehicles]
destinations = [structured_request.origin] * len(vehicles)

# Single API call for all distances
result = gmaps.distance_matrix(origins, destinations)
```

### 3. Use Templates During Development

```python
# Fast iteration during development
simulator = RequestSimulator(template_ratio=1.0)  # 100% templates

# Realistic evaluation for final testing
simulator = RequestSimulator(template_ratio=0.5)  # 50% LLM, 50% templates
```

## Understanding Metrics

### Parsing Accuracy

- **Origin/Destination Zone Accuracy**: Did you identify the correct neighborhood?
- **Location Error**: How far off were your coordinates? (in miles)
- **Time Constraint Accuracy**: Did you extract pickup/dropoff time windows correctly?

### Routing Efficiency

- **Net Revenue**: `Total Fare Revenue - Idle Cost`
  - Idle Cost = Deadhead Miles × $0.50/mile
  - Higher is better
- **Deadhead Ratio**: `Empty Miles / Total Miles`
  - Lower is better (0% = perfect, 100% = terrible)
- **Average Pickup Time**: Time to reach passenger
  - Lower is better

### Overall Score

Weighted combination:
```
Overall Score = 0.3 × Parsing Score + 0.7 × Routing Score
```

## Next Steps

1. **Review the Component Guide**: See `COMPONENT_GUIDE.md` for detailed documentation
2. **Implement NLP Parsing**: Use GPT-4/Claude to parse natural language
3. **Optimize Routing**: Implement better vehicle selection algorithms
4. **Scale Up**: Test with larger datasets
5. **Compare Strategies**: Evaluate multiple agents and compare results

## Troubleshooting

**Q: Why is my deadhead ratio still high (~17%)?**
A: The demo uses naive "first available vehicle" routing. Implement nearest-vehicle routing (see TODO.md Task 2) to reduce it to ~10%.

**Q: How do I use Google Maps API for exact coordinates?**
A: Set `GOOGLE_MAPS_API_KEY` environment variable and enable `augment_location=True` in demo script. But note: zone centers already give good results (~17% deadhead).

**Q: Can I run without API keys?**
A: Yes! The framework automatically uses zone center approximations. The demo produces realistic metrics without any API keys.

**Q: What if I see coordinates (0.0, 0.0)?**
A: This was a bug that has been fixed. The framework now automatically uses zone centers when coordinates are missing. Re-run the demo.

**Q: Where are the log files?**
A: Check `logs/evaluation.log` (text) and `logs/events.json` (structured events).

**Q: How do I visualize the routes?**
A: Parse `logs/events.json` and plot vehicle movements using matplotlib or folium:
```python
import json
import matplotlib.pyplot as plt

with open('logs/events.json') as f:
    events = json.load(f)

assignments = [e for e in events if e['event_type'] == 'VEHICLE_ASSIGNMENT']

for a in assignments:
    vehicle_loc = a['event_data']['current_location']
    pickup_loc = a['event_data']['pickup_location']

    plt.plot([vehicle_loc['longitude'], pickup_loc['longitude']],
             [vehicle_loc['latitude'], pickup_loc['latitude']], 'b-')

plt.xlabel('Longitude')
plt.ylabel('Latitude')
plt.title('Vehicle to Pickup Routes')
plt.show()
```

## Support

For issues or questions:
- Check `COMPONENT_GUIDE.md` for detailed documentation
- Review example implementations in `examples/`
- Open an issue on GitHub

Happy evaluating! 🚗
